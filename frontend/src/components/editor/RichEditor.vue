<script setup>
/**
 * RichEditor.vue — TipTap WYSIWYG Editör Bileşeni.
 *
 * XenForo uyumlu BB-Code çıktısı üreten zengin metin editörü.
 * 3 mod: Editör (WYSIWYG) | BB-Code (ham) | Önizleme
 */

import { ref, watch, onBeforeUnmount, computed } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'

import { htmlToBBCode, bbCodeToHtml, bbCodeToPreviewHtml } from '@/utils/bbcode-serializer'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled:   { type: Boolean, default: false },
  placeholder: { type: String, default: 'Makale içeriğinizi yazın...' },
})

const emit = defineEmits(['update:modelValue', 'change'])

// Editör modu: editor | bbcode | preview
const editorMode = ref('editor')

// BB-Code ham metin (ikincil mod)
const rawBBCode = ref('')

// AI menü state
const showAiMenu = ref(false)

// Link modal
const showLinkModal = ref(false)
const linkUrl = ref('')

// Resim modal
const showImageModal = ref(false)
const imageUrl = ref('')

// ── TipTap Editör ──────────────────────────────────────
const editor = useEditor({
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
    }),
    Underline,
    Link.configure({ openOnClick: false, HTMLAttributes: { class: 'editor-link' } }),
    Image.configure({ inline: false, allowBase64: true }),
    Placeholder.configure({ placeholder: props.placeholder }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
  ],
  editable: !props.disabled,
  content: bbCodeToHtml(props.modelValue) || '',
  onUpdate: ({ editor: e }) => {
    const html = e.getHTML()
    const bb = htmlToBBCode(html)
    rawBBCode.value = bb
    emit('update:modelValue', bb)
    emit('change')
  },
})

// BB-Code değişince editörü güncelle
watch(() => props.modelValue, (newVal) => {
  if (!editor.value) return
  const currentBB = htmlToBBCode(editor.value.getHTML())
  if (newVal !== currentBB) {
    editor.value.commands.setContent(bbCodeToHtml(newVal) || '', false)
    rawBBCode.value = newVal
  }
}, { immediate: false })

// Disabled durumu
watch(() => props.disabled, (val) => {
  editor.value?.setEditable(!val)
})

onBeforeUnmount(() => {
  editor.value?.destroy()
})

// ── Mod Değişimi ──────────────────────────────────────
function switchMode(mode) {
  if (mode === 'bbcode') {
    rawBBCode.value = htmlToBBCode(editor.value?.getHTML() || '')
  } else if (mode === 'editor' && editorMode.value === 'bbcode') {
    editor.value?.commands.setContent(bbCodeToHtml(rawBBCode.value) || '', false)
    emit('update:modelValue', rawBBCode.value)
  }
  editorMode.value = mode
}

// BB-Code textarea değişikliği
function onBBCodeInput() {
  emit('update:modelValue', rawBBCode.value)
  emit('change')
}

// ── Toolbar Aksiyonları ──────────────────────────────
function toggleBold()      { editor.value?.chain().focus().toggleBold().run() }
function toggleItalic()    { editor.value?.chain().focus().toggleItalic().run() }
function toggleUnderline() { editor.value?.chain().focus().toggleUnderline().run() }
function toggleStrike()    { editor.value?.chain().focus().toggleStrike().run() }
function setHeading(level) { editor.value?.chain().focus().toggleHeading({ level }).run() }
function toggleBulletList(){ editor.value?.chain().focus().toggleBulletList().run() }
function toggleOrderedList(){ editor.value?.chain().focus().toggleOrderedList().run() }
function toggleBlockquote(){ editor.value?.chain().focus().toggleBlockquote().run() }
function toggleCodeBlock() { editor.value?.chain().focus().toggleCodeBlock().run() }
function setHorizontalRule(){ editor.value?.chain().focus().setHorizontalRule().run() }
function undo()            { editor.value?.chain().focus().undo().run() }
function redo()            { editor.value?.chain().focus().redo().run() }
function alignLeft()       { editor.value?.chain().focus().setTextAlign('left').run() }
function alignCenter()     { editor.value?.chain().focus().setTextAlign('center').run() }
function alignRight()      { editor.value?.chain().focus().setTextAlign('right').run() }

function openLinkModal() {
  const prev = editor.value?.getAttributes('link').href || ''
  linkUrl.value = prev
  showLinkModal.value = true
}
function confirmLink() {
  if (linkUrl.value) {
    editor.value?.chain().focus().extendMarkRange('link').setLink({ href: linkUrl.value }).run()
  } else {
    editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
  }
  showLinkModal.value = false
}
function removeLink() {
  editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
  showLinkModal.value = false
}

function openImageModal() {
  imageUrl.value = ''
  showImageModal.value = true
}
function confirmImage() {
  if (imageUrl.value) {
    editor.value?.chain().focus().setImage({ src: imageUrl.value }).run()
  }
  showImageModal.value = false
}


// Aktif durumlar
const isActive = (name, attrs) => editor.value?.isActive(name, attrs) ?? false

// Önizleme HTML
const previewHtml = computed(() => bbCodeToPreviewHtml(
  editorMode.value === 'bbcode' ? rawBBCode.value : htmlToBBCode(editor.value?.getHTML() || '')
))

// Kelime sayısı
const wordCount = computed(() => {
  const text = editorMode.value === 'bbcode'
    ? rawBBCode.value.replace(/\[.*?\]/g, '').trim()
    : editor.value?.state.doc.textContent.trim() || ''
  return text ? text.split(/\s+/).length : 0
})

// AI Aksiyonları
const aiActions = [
  { id: 'expand',    icon: '📝', label: 'Genişlet',     desc: 'Seçili paragrafı daha detaylı yaz' },
  { id: 'rewrite',   icon: '🔄', label: 'Yeniden Yaz',  desc: 'Aynı anlam, farklı ifade' },
  { id: 'longer',    icon: '📖', label: 'Daha Uzun Yap', desc: 'Tüm metni genişlet' },
  { id: 'summarize', icon: '🎯', label: 'Özetle',       desc: 'Seçili bölümü kısalt' },
  { id: 'continue',  icon: '🔗', label: 'Devam Et',     desc: 'Metnin devamını yaz' },
  { id: 'translate', icon: '🌐', label: 'Çevir (İng→Tr)', desc: 'Seçili kısmı Türkçeye çevir' },
]

function handleAiAction(actionId) {
  showAiMenu.value = false
  const selectedText = editorMode.value === 'editor'
    ? editor.value?.state.doc.textBetween(
        editor.value.state.selection.from,
        editor.value.state.selection.to,
        ' '
      ) || ''
    : ''
  const fullText = editorMode.value === 'editor'
    ? editor.value?.state.doc.textContent || ''
    : rawBBCode.value

  emit('ai-action', { action: actionId, selectedText, fullText })
}

defineExpose({ editor, wordCount })
</script>

<template>
  <div class="rich-editor-wrapper">

    <!-- Mod Seçimi + Araç Çubuğu Üst Bar -->
    <div class="editor-topbar">
      <!-- Mod butonları -->
      <div class="mode-switcher">
        <button v-for="m in [
          { id: 'editor',  label: '✏️ Editör' },
          { id: 'bbcode',  label: '📝 BB-Code' },
          { id: 'preview', label: '👁 Önizleme' },
        ]" :key="m.id"
          @click="switchMode(m.id)"
          :class="['mode-btn', editorMode === m.id && 'mode-btn--active']">
          {{ m.label }}
        </button>
      </div>

      <div class="topbar-right">
        <span class="word-count">{{ wordCount }} kelime</span>
      </div>
    </div>

    <!-- Araç Çubuğu (sadece editor modunda) -->
    <div v-if="editorMode === 'editor' && !disabled" class="toolbar">
      <!-- Metin biçimlendirme -->
      <div class="toolbar-group">
        <button @click="toggleBold" :class="['tb', isActive('bold') && 'tb--active']" title="Kalın">B</button>
        <button @click="toggleItalic" :class="['tb', isActive('italic') && 'tb--active']" title="İtalik"><em>I</em></button>
        <button @click="toggleUnderline" :class="['tb', isActive('underline') && 'tb--active']" title="Altı çizili"><u>U</u></button>
        <button @click="toggleStrike" :class="['tb', isActive('strike') && 'tb--active']" title="Üstü çizili"><s>S</s></button>
      </div>

      <div class="toolbar-sep" />

      <!-- Başlıklar -->
      <div class="toolbar-group">
        <button @click="setHeading(1)" :class="['tb', isActive('heading', { level: 1 }) && 'tb--active']" title="Başlık 1">H1</button>
        <button @click="setHeading(2)" :class="['tb', isActive('heading', { level: 2 }) && 'tb--active']" title="Başlık 2">H2</button>
        <button @click="setHeading(3)" :class="['tb', isActive('heading', { level: 3 }) && 'tb--active']" title="Başlık 3">H3</button>
      </div>

      <div class="toolbar-sep" />

      <!-- Listeler + Blok -->
      <div class="toolbar-group">
        <button @click="toggleBulletList" :class="['tb', isActive('bulletList') && 'tb--active']" title="Sırasız liste">•</button>
        <button @click="toggleOrderedList" :class="['tb', isActive('orderedList') && 'tb--active']" title="Sıralı liste">1.</button>
        <button @click="toggleBlockquote" :class="['tb', isActive('blockquote') && 'tb--active']" title="Alıntı">❝</button>
        <button @click="toggleCodeBlock" :class="['tb', isActive('codeBlock') && 'tb--active']" title="Kod bloğu">&lt;/&gt;</button>
        <button @click="setHorizontalRule" class="tb" title="Yatay çizgi">―</button>
      </div>

      <div class="toolbar-sep" />

      <!-- Hizalama -->
      <div class="toolbar-group">
        <button @click="alignLeft" class="tb" title="Sola hizala">⫷</button>
        <button @click="alignCenter" class="tb" title="Ortala">☰</button>
        <button @click="alignRight" class="tb" title="Sağa hizala">⫸</button>
      </div>

      <div class="toolbar-sep" />

      <!-- Ekle -->
      <div class="toolbar-group">
        <button @click="openLinkModal" :class="['tb', isActive('link') && 'tb--active']" title="Link">🔗</button>
        <button @click="openImageModal" class="tb" title="Resim">🖼</button>
      </div>

      <div class="toolbar-sep" />

      <!-- Geri Al / Yinele -->
      <div class="toolbar-group">
        <button @click="undo" class="tb" title="Geri al">↩</button>
        <button @click="redo" class="tb" title="Yinele">↪</button>
      </div>

      <!-- AI Menü -->
      <div class="toolbar-group ml-auto relative">
        <button @click="showAiMenu = !showAiMenu"
                :class="['tb tb--ai', showAiMenu && 'tb--active']"
                title="AI Araçları">
          ✨ AI
        </button>

        <Transition name="fade">
          <div v-if="showAiMenu" class="ai-dropdown">
            <button v-for="a in aiActions" :key="a.id"
                    @click="handleAiAction(a.id)"
                    class="ai-dropdown-item">
              <span class="ai-icon">{{ a.icon }}</span>
              <div>
                <div class="ai-label">{{ a.label }}</div>
                <div class="ai-desc">{{ a.desc }}</div>
              </div>
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- ═══ Editör İçerik Alanları ═══ -->

    <!-- WYSIWYG Editör -->
    <div v-if="editorMode === 'editor'" class="editor-body">
      <EditorContent :editor="editor" class="tiptap-content" />
    </div>

    <!-- BB-Code Ham Metin -->
    <div v-else-if="editorMode === 'bbcode'" class="editor-body">
      <textarea
        v-model="rawBBCode"
        @input="onBBCodeInput"
        :disabled="disabled"
        class="bbcode-textarea"
        placeholder="BB-Code formatında içerik..."
        rows="20"
      />
    </div>

    <!-- Önizleme -->
    <div v-else-if="editorMode === 'preview'" class="editor-body">
      <div class="preview-area" v-html="previewHtml" />
    </div>

    <!-- ═══ Modal: Link ═══ -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showLinkModal" class="modal-overlay" @click.self="showLinkModal = false">
          <div class="modal-box">
            <h3 class="modal-title">🔗 Link Ekle</h3>
            <input v-model="linkUrl" type="url" class="modal-input" placeholder="https://..." @keyup.enter="confirmLink" />
            <div class="modal-actions">
              <button @click="removeLink" class="modal-btn modal-btn--danger">Kaldır</button>
              <button @click="showLinkModal = false" class="modal-btn">İptal</button>
              <button @click="confirmLink" class="modal-btn modal-btn--primary">Ekle</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ═══ Modal: Resim ═══ -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showImageModal" class="modal-overlay" @click.self="showImageModal = false">
          <div class="modal-box">
            <h3 class="modal-title">🖼 Resim Ekle</h3>
            <input v-model="imageUrl" type="url" class="modal-input" placeholder="https://... resim URL'si" @keyup.enter="confirmImage" />
            <div class="modal-actions">
              <button @click="showImageModal = false" class="modal-btn">İptal</button>
              <button @click="confirmImage" class="modal-btn modal-btn--primary">Ekle</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/* ── Wrapper ──────────────────────────────────── */
.rich-editor-wrapper {
  border: 1px solid rgba(55, 65, 81, 0.4);
  border-radius: 0.625rem;
  overflow: hidden;
  background: #0a0f1e;
}

/* ── Üst Bar ──────────────────────────────────── */
.editor-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.375rem 0.75rem;
  background: rgba(17, 24, 39, 0.8);
  border-bottom: 1px solid rgba(55, 65, 81, 0.3);
}

.mode-switcher {
  display: flex;
  gap: 2px;
  background: rgba(31, 41, 55, 0.5);
  border-radius: 0.5rem;
  padding: 2px;
}

.mode-btn {
  padding: 0.25rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #9ca3af;
  transition: all 0.15s;
  border: none;
  background: transparent;
  cursor: pointer;
}
.mode-btn:hover { color: #e5e7eb; }
.mode-btn--active {
  background: rgba(55, 65, 81, 0.8);
  color: #f3f4f6;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.topbar-right { display: flex; align-items: center; gap: 0.5rem; }
.word-count {
  font-size: 0.7rem;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
}

/* ── Araç Çubuğu ──────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0.375rem 0.5rem;
  background: rgba(17, 24, 39, 0.5);
  border-bottom: 1px solid rgba(55, 65, 81, 0.25);
  flex-wrap: wrap;
}

.toolbar-group { display: flex; gap: 1px; }
.toolbar-sep {
  width: 1px;
  height: 1.25rem;
  background: rgba(55, 65, 81, 0.4);
  margin: 0 0.25rem;
}

.tb {
  width: 1.75rem;
  height: 1.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: #9ca3af;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.1s;
}
.tb:hover {
  background: rgba(55, 65, 81, 0.5);
  color: #e5e7eb;
}
.tb--active {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}
.tb--ai {
  font-size: 0.7rem;
  padding: 0 0.5rem;
  width: auto;
  gap: 0.25rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(168, 85, 247, 0.08));
  border: 1px solid rgba(99, 102, 241, 0.15);
}
.tb--ai:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15));
  border-color: rgba(99, 102, 241, 0.3);
  color: #a78bfa;
}

.ml-auto { margin-left: auto; }
.relative { position: relative; }

/* ── AI Dropdown ──────────────────────────────── */
.ai-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.375rem;
  width: 260px;
  background: #1f2937;
  border: 1px solid rgba(75, 85, 99, 0.4);
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px rgba(0,0,0,0.4);
  z-index: 50;
  padding: 0.375rem;
}

.ai-dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  width: 100%;
  padding: 0.5rem 0.625rem;
  border-radius: 0.375rem;
  text-align: left;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.1s;
  color: #d1d5db;
}
.ai-dropdown-item:hover { background: rgba(55, 65, 81, 0.5); }
.ai-icon { font-size: 1rem; }
.ai-label { font-size: 0.8rem; font-weight: 500; }
.ai-desc  { font-size: 0.65rem; color: #6b7280; margin-top: 1px; }

/* ── Editör Gövde ─────────────────────────────── */
.editor-body { min-height: 400px; }

/* TipTap İçerik Alanı */
.tiptap-content { padding: 0; }
.tiptap-content :deep(.tiptap) {
  padding: 1.25rem;
  min-height: 400px;
  color: #e5e7eb;
  font-size: 0.9375rem;
  line-height: 1.8;
  outline: none;
}
.tiptap-content :deep(.tiptap p) { margin: 0.5rem 0; }
.tiptap-content :deep(.tiptap h1) { font-size: 1.75rem; font-weight: 700; margin: 1rem 0 0.5rem; color: #f3f4f6; }
.tiptap-content :deep(.tiptap h2) { font-size: 1.5rem; font-weight: 700; margin: 0.75rem 0; color: #f3f4f6; }
.tiptap-content :deep(.tiptap h3) { font-size: 1.25rem; font-weight: 600; margin: 0.5rem 0; color: #f3f4f6; }
.tiptap-content :deep(.tiptap strong) { font-weight: 700; color: #f9fafb; }
.tiptap-content :deep(.tiptap em) { font-style: italic; }
.tiptap-content :deep(.tiptap u) { text-decoration: underline; }
.tiptap-content :deep(.tiptap s) { text-decoration: line-through; color: #6b7280; }
.tiptap-content :deep(.tiptap ul),
.tiptap-content :deep(.tiptap ol) { padding-left: 1.5rem; margin: 0.5rem 0; }
.tiptap-content :deep(.tiptap li) { margin: 0.25rem 0; }
.tiptap-content :deep(.tiptap blockquote) {
  border-left: 3px solid #6366f1;
  padding: 0.5rem 1rem;
  margin: 0.5rem 0;
  color: #9ca3af;
  background: rgba(99, 102, 241, 0.05);
  border-radius: 0 0.375rem 0.375rem 0;
}
.tiptap-content :deep(.tiptap pre) {
  background: #1e293b;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
}
.tiptap-content :deep(.tiptap code) {
  background: #1e293b;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85em;
  font-family: 'Fira Code', monospace;
}
.tiptap-content :deep(.tiptap a),
.tiptap-content :deep(.tiptap .editor-link) {
  color: #818cf8;
  text-decoration: underline;
  cursor: pointer;
}
.tiptap-content :deep(.tiptap img) {
  max-width: 100%;
  border-radius: 0.5rem;
  margin: 0.5rem 0;
}
.tiptap-content :deep(.tiptap hr) {
  border: none;
  border-top: 1px solid rgba(55, 65, 81, 0.4);
  margin: 1rem 0;
}
.tiptap-content :deep(.tiptap table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5rem 0;
}
.tiptap-content :deep(.tiptap th),
.tiptap-content :deep(.tiptap td) {
  border: 1px solid rgba(55, 65, 81, 0.4);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
.tiptap-content :deep(.tiptap th) {
  background: rgba(31, 41, 55, 0.5);
  font-weight: 600;
  color: #d1d5db;
}
.tiptap-content :deep(.tiptap .is-empty::before) {
  content: attr(data-placeholder);
  color: #4b5563;
  pointer-events: none;
  float: left;
  height: 0;
}

/* BB-Code Textarea */
.bbcode-textarea {
  width: 100%;
  min-height: 400px;
  padding: 1.25rem;
  font-family: 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 0.875rem;
  line-height: 1.7;
  color: #e5e7eb;
  background: transparent;
  border: none;
  resize: vertical;
  outline: none;
}
.bbcode-textarea:disabled { opacity: 0.6; cursor: not-allowed; }

/* Önizleme */
.preview-area {
  min-height: 400px;
  padding: 1.25rem;
  font-size: 0.9375rem;
  line-height: 1.8;
  color: #d1d5db;
  overflow-y: auto;
}

/* ── Modallar ─────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.modal-box {
  background: #1f2937;
  border: 1px solid rgba(75, 85, 99, 0.4);
  border-radius: 0.75rem;
  padding: 1.5rem;
  width: 400px;
  max-width: 90vw;
}
.modal-title {
  font-size: 1rem;
  font-weight: 600;
  color: #f3f4f6;
  margin-bottom: 1rem;
}
.modal-input {
  width: 100%;
  padding: 0.625rem 0.75rem;
  background: #111827;
  border: 1px solid rgba(55, 65, 81, 0.5);
  border-radius: 0.5rem;
  color: #e5e7eb;
  font-size: 0.875rem;
  outline: none;
  margin-bottom: 1rem;
}
.modal-input:focus { border-color: rgba(99, 102, 241, 0.5); }
.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
.modal-btn {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid rgba(55, 65, 81, 0.4);
  background: rgba(55, 65, 81, 0.3);
  color: #d1d5db;
  transition: all 0.15s;
}
.modal-btn:hover { background: rgba(55, 65, 81, 0.5); }
.modal-btn--primary {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
}
.modal-btn--primary:hover { background: rgba(99, 102, 241, 0.25); }
.modal-btn--danger {
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.3);
}
.modal-btn--danger:hover { background: rgba(239, 68, 68, 0.1); }

/* ── Animasyonlar ─────────────────────────────── */
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
