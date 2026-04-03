<script setup>
/**
 * DevOpsView.vue — Sistem & Tema Yönetimi
 * 
 * 4 Sekme:
 *   1. Sistem Durumu  — PHP sürümü, disk, bellek, SSH bağlantısı
 *   2. SSH Terminali  — Canlı komut çalıştırma (SSE stream)
 *   3. XenForo Güncelleyici — Fail-safe pipeline (yedek→bakım→upgrade→açık)
 *   4. Tema Editörü   — Monaco editör + dosya ağacı + önbellek temizleme
 */

import { ref, computed, onMounted } from 'vue'
import api          from '@/services/api'
import MonacoEditor from '@/components/ui/MonacoEditor.vue'

// ── Aktif sekme ──────────────────────────────────────────
const activeTab = ref('status')

// ═══════════════════════════════════════════════════════
// SEKME 1: SİSTEM DURUMU
// ═══════════════════════════════════════════════════════
const sysStatus     = ref(null)
const statusLoading = ref(false)
const sshOnline     = ref(null)

async function checkStatus() {
  statusLoading.value = true
  sshOnline.value     = null
  try {
    const [healthRes, statusRes] = await Promise.all([
      api.get('/ssh/health'),
      api.get('/updater/status'),
    ])
    sshOnline.value  = healthRes.data.success
    sysStatus.value  = statusRes.data.data
  } catch (e) {
    sshOnline.value = false
    sysStatus.value = { error: e.response?.data?.message || String(e) }
  } finally {
    statusLoading.value = false
  }
}

onMounted(checkStatus)

// ═══════════════════════════════════════════════════════
// SEKME 2: SSH TERMİNAL
// ═══════════════════════════════════════════════════════
const termLines   = ref([])
const termInput   = ref('')
const termRunning = ref(false)
let   termEs      = null   // EventSource

const QUICK_CMDS = [
  { label: 'Disk Kullanımı',  cmd: 'df -h' },
  { label: 'Bellek',          cmd: 'free -h' },
  { label: 'Çalışan Süreçler', cmd: 'ps aux | head -20' },
  { label: 'PHP Sürümü',      cmd: 'php -v' },
  { label: 'Uptime',          cmd: 'uptime' },
  { label: 'XF Sürümü',       cmd: "grep 'versionString\\|version =' src/XF/App.php | head -3" },
]

function runQuick(cmd) { termInput.value = cmd; runCommand() }

function runCommand() {
  const cmd = termInput.value.trim()
  if (!cmd || termRunning.value) return

  termLines.value.push({ type: 'input', text: `$ ${cmd}` })
  termRunning.value = true

  // SSE stream
  fetch('/api/ssh/exec/stream', {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    },
    body: JSON.stringify({ command: cmd, timeout: 120 }),
  }).then(resp => {
    const reader = resp.body.getReader()
    const dec    = new TextDecoder()
    let   buf    = ''

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) { termRunning.value = false; return }
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop()   // son parça tamamlanmamış olabilir
        for (const part of parts) {
          const line = part.replace(/^data: /, '').trim()
          if (!line) continue
          try {
            const obj = JSON.parse(line)
            if (obj.done) {
              termRunning.value = false
              termLines.value.push({
                type: obj.exit_code === 0 ? 'ok' : 'err',
                text: `[exit: ${obj.exit_code}]`,
              })
            } else {
              termLines.value.push({
                type: obj.stream === 'stderr' ? 'err' : 'out',
                text: obj.line,
              })
            }
          } catch {}
        }
        // Auto-scroll
        setTimeout(() => {
          const el = document.getElementById('term-output')
          if (el) el.scrollTop = el.scrollHeight
        }, 10)
        read()
      })
    }
    read()
  }).catch(e => {
    termLines.value.push({ type: 'err', text: String(e) })
    termRunning.value = false
  })

  termInput.value = ''
}

function clearTerm() { termLines.value = [] }

// ═══════════════════════════════════════════════════════
// SEKME 3: XENFORO GÜNCELLEYİCİ
// ═══════════════════════════════════════════════════════
const upgradeLines   = ref([])
const upgradeRunning = ref(false)
const upgradeResult  = ref(null)   // {success, error}

async function startUpgrade() {
  if (upgradeRunning.value) return
  if (!confirm('⚠️ XenForo güncelleme başlatılacak.\n\nÖnce DB ve dosya yedeği alınacak. Devam etmek istiyor musunuz?')) return

  upgradeLines.value  = []
  upgradeRunning.value = true
  upgradeResult.value  = null

  fetch('/api/updater/upgrade/stream', {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    },
    body: JSON.stringify({}),
  }).then(resp => {
    const reader = resp.body.getReader()
    const dec    = new TextDecoder()
    let   buf    = ''

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) { upgradeRunning.value = false; return }
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop()
        for (const part of parts) {
          const line = part.replace(/^data: /, '').trim()
          if (!line) continue
          try {
            const obj = JSON.parse(line)
            if (obj.done !== undefined) {
              upgradeRunning.value = false
              upgradeResult.value  = { success: obj.success, error: obj.error }
            } else {
              upgradeLines.value.push({
                type: obj.stream || 'out',
                text: obj.line || JSON.stringify(obj),
              })
            }
          } catch {}
        }
        const el = document.getElementById('upgrade-output')
        if (el) el.scrollTop = el.scrollHeight
        read()
      })
    }
    read()
  }).catch(e => {
    upgradeLines.value.push({ type: 'err', text: String(e) })
    upgradeRunning.value = false
  })
}

async function clearXFCache() {
  try {
    const { data } = await api.post('/updater/cache/clear', { targets: ['templates', 'addons'] })
    upgradeLines.value.push({ type: 'ok', text: `✓ Önbellek temizlendi: ${JSON.stringify(data.data)}` })
  } catch (e) {
    upgradeLines.value.push({ type: 'err', text: `Önbellek hatası: ${e.response?.data?.error || e}` })
  }
}

// ═══════════════════════════════════════════════════════
// SEKME 4: TEMA EDİTÖRÜ
// ═══════════════════════════════════════════════════════
const themeFiles    = ref([])
const themeLoading  = ref(false)
const selectedFile  = ref(null)   // {path, content, extension}
const editorContent = ref('')
const isSaving      = ref(false)
const saveResult    = ref(null)
const clearingCache = ref(false)

async function loadThemeFiles() {
  themeLoading.value = true
  try {
    const { data } = await api.get('/theme/files', { params: { recursive: 1 } })
    themeFiles.value = buildTree(data.data || [])
  } catch (e) {
    console.error('Tema dosyaları yüklenemedi:', e)
  } finally {
    themeLoading.value = false
  }
}

function buildTree(flat) {
  // Basit ağaç: dizinleri üste grupla
  const dirs  = flat.filter(f => f.is_dir).sort((a, b) => a.name.localeCompare(b.name))
  const files = flat.filter(f => !f.is_dir).sort((a, b) => a.name.localeCompare(b.name))
  return [...dirs, ...files]
}

async function openFile(file) {
  if (file.is_dir) return
  try {
    const { data } = await api.get('/theme/file', { params: { path: file.path } })
    selectedFile.value  = data.data
    editorContent.value = data.data.content
    saveResult.value    = null
  } catch (e) {
    alert(`Dosya açılamadı: ${e.response?.data?.error || e}`)
  }
}

async function saveFile() {
  if (!selectedFile.value || isSaving.value) return
  isSaving.value = true
  saveResult.value = null
  try {
    const { data } = await api.post('/theme/file', {
      path:    selectedFile.value.path,
      content: editorContent.value,
      backup:  true,
    })
    saveResult.value = { success: true, backup: data.data.backup_path }
  } catch (e) {
    saveResult.value = { success: false, error: e.response?.data?.error || String(e) }
  } finally {
    isSaving.value = false
  }
}

async function clearThemeCache() {
  clearingCache.value = true
  try {
    const { data } = await api.post('/theme/cache')
    saveResult.value = { success: true, cache: data.data }
  } catch (e) {
    saveResult.value = { success: false, error: String(e) }
  } finally {
    clearingCache.value = false
  }
}

const editorLang = computed(() => selectedFile.value?.extension?.replace('.', '') || 'plaintext')

// Dosya tipi renkleri
const EXT_COLOR = {
  '.less':  'text-purple-400', '.css':  'text-sky-400',
  '.html':  'text-amber-400',  '.php':  'text-indigo-400',
  '.js':    'text-yellow-400', '.json': 'text-green-400',
}
function extColor(f) { return EXT_COLOR[f.extension] || 'text-gray-400' }
function fileIcon(f) {
  if (f.is_dir) return '📁'
  const icons = { '.less':'🎨','.css':'🎨','.html':'🔷','.php':'🐘','.js':'⚡','.json':'📋', '.xml':'📄' }
  return icons[f.extension] || '📄'
}
</script>

<template>
  <div class="max-w-screen-xl mx-auto space-y-5 animate-fade-in">

    <!-- Başlık + SSH durumu -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-xl font-bold text-gray-100">Sistem & Tema Yönetimi</h1>
        <p class="text-sm text-gray-500">SSH, DevOps güncelleyici ve tema editörü</p>
      </div>
      <span v-if="sshOnline === true"
            class="flex items-center gap-1.5 text-xs text-emerald-400
                   bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full">
        <span class="live-dot" /> SSH Bağlı
      </span>
      <span v-else-if="sshOnline === false"
            class="text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-3 py-1 rounded-full">
        ✕ SSH Bağlantı Hatası
      </span>
    </div>

    <!-- Sekme butonları -->
    <div class="flex flex-wrap gap-1 bg-gray-900 rounded-xl p-1 w-fit">
      <button v-for="tab in [
        { id: 'status',   label: '📊 Sistem Durumu' },
        { id: 'terminal', label: '⌨️ SSH Terminal' },
        { id: 'upgrade',  label: '🚀 XF Güncelleyici' },
        { id: 'theme',    label: '🎨 Tema Editörü' },
      ]" :key="tab.id"
      @click="activeTab = tab.id; tab.id==='theme' && !themeFiles.length && loadThemeFiles()"
      :class="['px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150',
               activeTab === tab.id
                 ? 'bg-gray-800 text-gray-100 shadow-md'
                 : 'text-gray-400 hover:text-gray-200']">
        {{ tab.label }}
      </button>
    </div>

    <!-- ══ SEKME 1: SİSTEM DURUMU ═════════════════════════ -->
    <div v-if="activeTab === 'status'" class="animate-fade-in space-y-4">
      <div class="card p-6 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-300">Sunucu Bilgileri</h2>
          <button @click="checkStatus" class="btn-ghost text-xs px-3 py-1.5"
                  :disabled="statusLoading">
            {{ statusLoading ? '…' : '↺ Yenile' }}
          </button>
        </div>

        <div v-if="statusLoading" class="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <div v-for="i in 6" :key="i"
               class="h-20 bg-gray-700/40 animate-pulse rounded-xl" />
        </div>

        <div v-else-if="sysStatus" class="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <div v-for="(val, key) in sysStatus" :key="key"
               class="bg-gray-900/60 rounded-xl p-4">
            <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">
              {{ { php_version:'PHP',disk_usage:'Disk',xf_version:'XenForo',
                   uptime:'Uptime',memory:'Bellek',error:'Hata' }[key] || key }}
            </p>
            <p :class="['text-sm font-medium break-all',
                        key==='error' ? 'text-red-400' : 'text-gray-200']">
              {{ val || '—' }}
            </p>
          </div>
        </div>

        <div v-if="sshOnline === false"
             class="bg-red-500/5 border border-red-500/20 p-4 rounded-lg text-xs text-red-300 space-y-1">
          <p class="font-medium">SSH bağlantısı kurulamıyor.</p>
          <p class="text-red-400/70">.env dosyasındaki SSH_HOST, SSH_USERNAME ve SSH_PASSWORD/SSH_PRIVATE_KEY_PATH değerlerini kontrol edin.</p>
        </div>
      </div>
    </div>

    <!-- ══ SEKME 2: SSH TERMİNAL ══════════════════════════ -->
    <div v-if="activeTab === 'terminal'" class="animate-fade-in space-y-4">

      <!-- Hızlı komutlar -->
      <div class="card p-4">
        <p class="text-xs text-gray-500 mb-2">Hızlı Komutlar</p>
        <div class="flex flex-wrap gap-2">
          <button v-for="q in QUICK_CMDS" :key="q.cmd"
                  @click="runQuick(q.cmd)"
                  class="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700
                         border border-gray-700 rounded-lg text-gray-300
                         transition-colors disabled:opacity-50"
                  :disabled="termRunning">
            {{ q.label }}
          </button>
        </div>
      </div>

      <!-- Terminal ekranı -->
      <div class="card overflow-hidden">
        <!-- Terminal başlığı -->
        <div class="flex items-center gap-2 px-4 py-2.5 bg-gray-950 border-b border-gray-700/50">
          <span class="w-3 h-3 rounded-full bg-red-500/70" />
          <span class="w-3 h-3 rounded-full bg-amber-500/70" />
          <span class="w-3 h-3 rounded-full bg-emerald-500/70" />
          <span class="text-xs text-gray-500 ml-2 font-mono">SSH Terminal — {{ sshOnline ? 'Bağlı' : '…' }}</span>
          <button @click="clearTerm" class="ml-auto text-xs text-gray-600 hover:text-gray-400">Temizle</button>
        </div>

        <!-- Çıktı -->
        <div id="term-output"
             class="font-mono text-xs leading-5 h-80 overflow-y-auto p-4
                    bg-gray-950 space-y-px">
          <div v-if="!termLines.length" class="text-gray-700">
            Komut girin veya yukarıdan hızlı komut seçin…
          </div>
          <div v-for="(l, i) in termLines" :key="i"
               :class="[
                 'whitespace-pre-wrap break-all',
                 l.type === 'input' ? 'text-indigo-400' :
                 l.type === 'err'   ? 'text-red-400' :
                 l.type === 'ok'    ? 'text-emerald-400' : 'text-gray-300',
               ]">{{ l.text }}</div>
          <div v-if="termRunning" class="text-amber-400 animate-pulse">▌</div>
        </div>

        <!-- Giriş -->
        <div class="flex items-center gap-2 px-4 py-3 bg-gray-950 border-t border-gray-700/30">
          <span class="text-indigo-400 font-mono text-xs select-none">$</span>
          <input v-model="termInput"
                 @keyup.enter="runCommand"
                 class="flex-1 bg-transparent font-mono text-xs text-gray-200
                        outline-none placeholder-gray-700"
                 placeholder="komut girin… (Enter)"
                 :disabled="termRunning" />
          <button @click="runCommand" class="btn-primary text-xs px-3 py-1.5"
                  :disabled="!termInput.trim() || termRunning">
            {{ termRunning ? '…' : 'Çalıştır' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ══ SEKME 3: XENFORO GÜNCELLEYİCİ ═════════════════ -->
    <div v-if="activeTab === 'upgrade'" class="animate-fade-in space-y-4">
      <div class="card p-6 space-y-4">
        <div>
          <h2 class="text-sm font-semibold text-gray-300">XenForo Sürüm Güncelleyici</h2>
          <p class="text-xs text-gray-500 mt-1">
            Güncelleme başlamadan önce DB + dosya yedeği alınır.
            Yedek başarısız olursa süreç iptal edilir.
          </p>
        </div>

        <!-- Adım göstergesi -->
        <div class="flex items-center gap-0">
          <div v-for="(step, i) in ['DB Yedek','Dosya Yedek','Bakım Modu','xf:upgrade','Tamamlandı']"
               :key="i"
               class="flex items-center">
            <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs
                        bg-gray-800 border border-gray-700 text-gray-500">
              {{ i + 1 }}
            </div>
            <div class="text-xs text-gray-600 mx-1 hidden sm:block">{{ step }}</div>
            <div v-if="i < 4" class="w-6 h-px bg-gray-700 mx-1" />
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button @click="startUpgrade"
                  class="btn-danger flex items-center gap-2"
                  :disabled="upgradeRunning || !sshOnline">
            <span v-if="upgradeRunning" class="animate-spin-slow">⚙</span>
            🚀 Güncellemeyi Başlat
          </button>
          <button @click="clearXFCache" class="btn-ghost text-xs" :disabled="upgradeRunning">
            🗑 Önbellek Temizle
          </button>
        </div>

        <!-- Sonuç mesajı -->
        <div v-if="upgradeResult"
             :class="['p-3 rounded-lg text-sm font-medium',
                      upgradeResult.success
                        ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                        : 'bg-red-500/10 border border-red-500/20 text-red-400']">
          {{ upgradeResult.success
              ? '✓ XenForo başarıyla güncellendi!'
              : `✕ Güncelleme başarısız: ${upgradeResult.error}` }}
        </div>
      </div>

      <!-- Pipeline çıktısı -->
      <div class="card overflow-hidden">
        <div class="px-4 py-2.5 bg-gray-950 border-b border-gray-700/50 flex items-center gap-2">
          <span class="font-mono text-xs text-gray-500">Pipeline Çıktısı</span>
          <span v-if="upgradeRunning" class="text-xs text-amber-400 animate-pulse ml-2">■ Çalışıyor</span>
        </div>
        <div id="upgrade-output"
             class="font-mono text-xs leading-5 h-72 overflow-y-auto p-4 bg-gray-950 space-y-px">
          <div v-if="!upgradeLines.length" class="text-gray-700">
            Pipeline başlatıldığında çıktı burada görünür…
          </div>
          <div v-for="(l, i) in upgradeLines" :key="i"
               :class="[
                 'whitespace-pre-wrap',
                 l.type === 'abort' || l.type === 'error' ? 'text-red-400' :
                 l.type === 'ok'   ? 'text-emerald-400' :
                 l.type === 'info' ? 'text-indigo-400' :
                 l.type === 'step' ? 'text-amber-400' : 'text-gray-300',
               ]">{{ l.text }}</div>
          <div v-if="upgradeRunning" class="text-amber-400 animate-pulse">▌</div>
        </div>
      </div>
    </div>

    <!-- ══ SEKME 4: TEMA EDİTÖRÜ ══════════════════════════ -->
    <div v-if="activeTab === 'theme'" class="animate-fade-in">
      <div class="grid grid-cols-1 xl:grid-cols-4 gap-4">

        <!-- Dosya ağacı (sol panel) -->
        <div class="xl:col-span-1 card p-0 overflow-hidden">
          <div class="flex items-center justify-between px-3 py-2.5
                      border-b border-gray-700/40 bg-gray-900/60">
            <span class="text-xs font-semibold text-gray-400">styles/</span>
            <button @click="loadThemeFiles" class="text-xs text-gray-500 hover:text-gray-300"
                    :disabled="themeLoading">
              {{ themeLoading ? '…' : '↺' }}
            </button>
          </div>

          <div class="overflow-y-auto max-h-[600px]">
            <!-- Yükleniyor -->
            <div v-if="themeLoading" class="p-3 space-y-1.5">
              <div v-for="i in 8" :key="i"
                   class="h-7 bg-gray-700/40 animate-pulse rounded" />
            </div>

            <!-- Boş -->
            <div v-else-if="!themeFiles.length"
                 class="p-4 text-xs text-gray-600 text-center">
              SSH bağlantısı yoksa dosyalar listelenemez.
            </div>

            <!-- Liste -->
            <div v-else class="py-1">
              <button v-for="file in themeFiles" :key="file.path"
                      @click="openFile(file)"
                      :class="[
                        'w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors',
                        selectedFile?.path === file.path
                          ? 'bg-indigo-500/10 text-indigo-300'
                          : 'hover:bg-gray-700/20 text-gray-400',
                        file.is_dir ? 'font-medium text-gray-300' : 'text-sm',
                      ]">
                <span class="text-sm shrink-0">{{ fileIcon(file) }}</span>
                <span :class="['text-xs truncate', extColor(file)]">{{ file.name }}</span>
                <span v-if="!file.is_dir && file.size"
                      class="text-gray-700 text-[10px] ml-auto shrink-0">
                  {{ (file.size / 1024).toFixed(1) }}K
                </span>
              </button>
            </div>
          </div>
        </div>

        <!-- Monaco Editör (sağ panel) -->
        <div class="xl:col-span-3 space-y-3">

          <!-- Editör başlığı -->
          <div class="card p-0 overflow-hidden">
            <div class="flex items-center justify-between px-4 py-2.5
                        bg-gray-900/60 border-b border-gray-700/40">
              <div class="flex items-center gap-2">
                <span class="text-sm">{{ selectedFile ? fileIcon(selectedFile) : '📄' }}</span>
                <span class="font-mono text-xs text-gray-300 truncate max-w-xs">
                  {{ selectedFile?.path?.split('/').slice(-2).join('/') || 'Dosya seçilmedi' }}
                </span>
                <span v-if="selectedFile"
                      class="text-xs px-1.5 py-0.5 bg-gray-800 rounded text-gray-500 font-mono">
                  {{ selectedFile.extension }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <button v-if="selectedFile" @click="clearThemeCache"
                        class="btn-ghost text-xs px-2.5 py-1.5"
                        :disabled="clearingCache">
                  {{ clearingCache ? '…' : '🗑 Önbellek' }}
                </button>
                <button v-if="selectedFile" @click="saveFile"
                        class="btn-primary text-xs px-3 py-1.5 gap-1"
                        :disabled="isSaving || !sshOnline">
                  <span v-if="isSaving" class="animate-spin-slow text-xs">⚙</span>
                  {{ isSaving ? 'Kaydediliyor…' : '💾 Kaydet (Ctrl+S)' }}
                </button>
              </div>
            </div>

            <!-- Bildirimler -->
            <div v-if="saveResult"
                 :class="['px-4 py-2 text-xs border-b',
                          saveResult.success
                            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                            : 'bg-red-500/10 border-red-500/20 text-red-400']">
              <span v-if="saveResult.success">
                ✓ Kaydedildi.
                <span v-if="saveResult.backup" class="text-emerald-500/60">
                  Yedek: {{ saveResult.backup?.split('/').pop() }}
                </span>
                <span v-if="saveResult.cache">| Önbellek: {{ Object.keys(saveResult.cache).join(', ') }}</span>
              </span>
              <span v-else>✕ {{ saveResult.error }}</span>
            </div>

            <!-- Monaco -->
            <MonacoEditor
              v-if="selectedFile"
              v-model="editorContent"
              :language="editorLang"
              height="560px"
              @save="saveFile"
            />
            <div v-else
                 class="h-96 flex flex-col items-center justify-center text-gray-700">
              <div class="text-4xl mb-3">🎨</div>
              <p class="text-sm">Sol panelden bir dosya seçin</p>
              <p class="text-xs mt-1">styles/ dizinini SSH üzerinden okur</p>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
#term-output::-webkit-scrollbar  { width: 4px; }
#term-output::-webkit-scrollbar-track  { background: transparent; }
#term-output::-webkit-scrollbar-thumb  { background: #374151; border-radius: 2px; }
#upgrade-output::-webkit-scrollbar     { width: 4px; }
#upgrade-output::-webkit-scrollbar-thumb { background: #374151; border-radius: 2px; }
</style>
