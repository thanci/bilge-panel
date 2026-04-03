<script setup>
/**
 * MonacoEditor.vue — Monaco kod editörü (CDN üzerinden yüklenir).
 * 
 * Monaco'yu npm ile yüklemek yerine CDN'den AMD loader kullanılır.
 * Bu yaklaşım bundle boyutunu ~5MB azaltır.
 * 
 * Özellikler:
 *   - Dil: dosya uzantısına göre otomatik (less, css, html, php, js, json...)
 *   - Tema: vs-dark (Bilge Yolcu dark mode ile uyumlu)
 *   - Ctrl+S ile kaydet event'i emit eder
 *   - Readonly modu (diff viewer için)
 */

import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  language:   { type: String, default: 'plaintext' },
  readOnly:   { type: Boolean, default: false },
  height:     { type: String, default: '500px' },
})

const emit = defineEmits(['update:modelValue', 'save'])

const containerRef = ref(null)
let editor    = null
let monacoLib = null
let isUpdating = false

// Uzantı → Monaco dil eşlemesi
const EXT_LANG = {
  '.less':  'less',
  '.css':   'css',
  '.html':  'html',
  '.tpl':   'html',
  '.php':   'php',
  '.js':    'javascript',
  '.json':  'json',
  '.xml':   'xml',
  '.md':    'markdown',
  '.txt':   'plaintext',
  '.sh':    'shell',
  '.py':    'python',
}

function langFromExt(ext) {
  return EXT_LANG[ext?.toLowerCase()] ?? 'plaintext'
}

// Monaco CDN yükleme (AMD require)
function loadMonaco() {
  return new Promise((resolve, reject) => {
    if (window.monaco) { resolve(window.monaco); return }
    if (window._monacoLoading) {
      const check = setInterval(() => {
        if (window.monaco) { clearInterval(check); resolve(window.monaco) }
      }, 100)
      return
    }
    window._monacoLoading = true

    const loader = document.createElement('script')
    loader.src   = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.min.js'
    loader.onload = () => {
      window.require.config({
        paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }
      })
      window.require(['vs/editor/editor.main'], (monaco) => {
        window.monaco = monaco
        window._monacoLoading = false
        resolve(monaco)
      })
    }
    loader.onerror = reject
    document.head.appendChild(loader)
  })
}

onMounted(async () => {
  try {
    monacoLib = await loadMonaco()
    await nextTick()

    editor = monacoLib.editor.create(containerRef.value, {
      value:            props.modelValue,
      language:         langFromExt(props.language) || langFromExt(`.${props.language}`),
      theme:            'vs-dark',
      readOnly:         props.readOnly,
      fontSize:         13,
      fontFamily:       "'JetBrains Mono', 'Fira Code', monospace",
      lineHeight:       22,
      minimap:          { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout:  true,
      tabSize:          2,
      wordWrap:         'on',
      padding:          { top: 12, bottom: 12 },
    })

    // İçerik değişince emit — model'i güncelle
    editor.onDidChangeModelContent(() => {
      if (!isUpdating) {
        emit('update:modelValue', editor.getValue())
      }
    })

    // Ctrl+S → save event
    editor.addCommand(
      monacoLib.KeyMod.CtrlCmd | monacoLib.KeyCode.KeyS,
      () => emit('save', editor.getValue()),
    )
  } catch (e) {
    console.error('[Monaco] Yüklenemedi:', e)
  }
})

// Dışarıdan prop değişirse editörü güncelle
watch(() => props.modelValue, (val) => {
  if (editor && editor.getValue() !== val) {
    isUpdating = true
    editor.setValue(val ?? '')
    isUpdating = false
  }
})

// Dil değişirse
watch(() => props.language, (lang) => {
  if (editor && monacoLib) {
    const newLang = langFromExt(lang) || langFromExt(`.${lang}`)
    monacoLib.editor.setModelLanguage(editor.getModel(), newLang)
  }
})

onBeforeUnmount(() => {
  editor?.dispose()
})
</script>

<template>
  <div class="w-full rounded-lg overflow-hidden border border-gray-700/50"
       :style="{ height }">
    <div ref="containerRef" class="w-full h-full" />
  </div>
</template>
