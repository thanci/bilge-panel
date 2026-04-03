/**
 * bbcode-serializer.js — TipTap JSON ↔ BB-Code dönüştürücü.
 *
 * TipTap editörün HTML çıktısını XenForo uyumlu BB-Code'a çevirir.
 * Ayrıca mevcut BB-Code içeriğini TipTap'ın anlayacağı HTML'e dönüştürür.
 */

// ── HTML → BB-Code ────────────────────────────────────────
export function htmlToBBCode(html) {
  if (!html) return ''

  let bb = html

  // Blok elemanları önce (sıralama önemli)
  bb = bb.replace(/<h1[^>]*>(.*?)<\/h1>/gi, '[HEADING=1]$1[/HEADING]\n')
  bb = bb.replace(/<h2[^>]*>(.*?)<\/h2>/gi, '[HEADING=2]$1[/HEADING]\n')
  bb = bb.replace(/<h3[^>]*>(.*?)<\/h3>/gi, '[HEADING=3]$1[/HEADING]\n')

  // Listeler
  bb = bb.replace(/<ul[^>]*>([\s\S]*?)<\/ul>/gi, (_, inner) => {
    const items = inner.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, '[*]$1\n')
    return '[LIST]\n' + items + '[/LIST]\n'
  })
  bb = bb.replace(/<ol[^>]*>([\s\S]*?)<\/ol>/gi, (_, inner) => {
    const items = inner.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, '[*]$1\n')
    return '[LIST=1]\n' + items + '[/LIST]\n'
  })

  // Blockquote
  bb = bb.replace(/<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi, '[QUOTE]$1[/QUOTE]\n')

  // Tablo
  bb = bb.replace(/<table[^>]*>([\s\S]*?)<\/table>/gi, (_, inner) => {
    // Basit tablo dönüşümü
    let rows = ''
    const trMatches = inner.match(/<tr[^>]*>([\s\S]*?)<\/tr>/gi) || []
    for (const tr of trMatches) {
      const cells = []
      const cellMatches = tr.match(/<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/gi) || []
      for (const cell of cellMatches) {
        cells.push(cell.replace(/<\/?t[hd][^>]*>/gi, '').trim())
      }
      rows += cells.join(' | ') + '\n'
    }
    return rows
  })

  // Kod bloğu
  bb = bb.replace(/<pre[^>]*><code[^>]*>([\s\S]*?)<\/code><\/pre>/gi, '[CODE]$1[/CODE]\n')
  bb = bb.replace(/<code[^>]*>([\s\S]*?)<\/code>/gi, '[ICODE]$1[/ICODE]')

  // İnline stil
  bb = bb.replace(/<strong[^>]*>(.*?)<\/strong>/gi, '[B]$1[/B]')
  bb = bb.replace(/<b[^>]*>(.*?)<\/b>/gi, '[B]$1[/B]')
  bb = bb.replace(/<em[^>]*>(.*?)<\/em>/gi, '[I]$1[/I]')
  bb = bb.replace(/<i[^>]*>(.*?)<\/i>/gi, '[I]$1[/I]')
  bb = bb.replace(/<u[^>]*>(.*?)<\/u>/gi, '[U]$1[/U]')
  bb = bb.replace(/<s[^>]*>(.*?)<\/s>/gi, '[S]$1[/S]')
  bb = bb.replace(/<del[^>]*>(.*?)<\/del>/gi, '[S]$1[/S]')
  bb = bb.replace(/<mark[^>]*>(.*?)<\/mark>/gi, '$1')

  // Link
  bb = bb.replace(/<a\s+href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '[URL=$1]$2[/URL]')

  // Resim
  bb = bb.replace(/<img\s+src="([^"]*)"[^>]*\/?>/gi, '[IMG]$1[/IMG]')

  // Yatay çizgi
  bb = bb.replace(/<hr[^>]*\/?>/gi, '[HR][/HR]\n')

  // Text align
  bb = bb.replace(/<p[^>]*style="text-align:\s*center[^"]*"[^>]*>(.*?)<\/p>/gi, '[CENTER]$1[/CENTER]\n')
  bb = bb.replace(/<p[^>]*style="text-align:\s*right[^"]*"[^>]*>(.*?)<\/p>/gi, '[RIGHT]$1[/RIGHT]\n')

  // Paragraflar
  bb = bb.replace(/<p[^>]*>(.*?)<\/p>/gi, '$1\n')

  // Line breaks
  bb = bb.replace(/<br\s*\/?>/gi, '\n')

  // Kalan HTML etiketlerini temizle
  bb = bb.replace(/<[^>]+>/g, '')

  // HTML entities
  bb = bb.replace(/&amp;/g, '&')
  bb = bb.replace(/&lt;/g, '<')
  bb = bb.replace(/&gt;/g, '>')
  bb = bb.replace(/&quot;/g, '"')
  bb = bb.replace(/&#39;/g, "'")
  bb = bb.replace(/&nbsp;/g, ' ')

  // Fazla boş satırları temizle
  bb = bb.replace(/\n{3,}/g, '\n\n')

  return bb.trim()
}


// ── BB-Code → HTML ────────────────────────────────────────
export function bbCodeToHtml(bbcode) {
  if (!bbcode) return ''

  let html = bbcode

  // Newlines → <br> (paragraflar öncekinden sonra)
  html = html.replace(/\n/g, '<br>')

  // Inline
  html = html.replace(/\[B\]([\s\S]*?)\[\/B\]/gi, '<strong>$1</strong>')
  html = html.replace(/\[I\]([\s\S]*?)\[\/I\]/gi, '<em>$1</em>')
  html = html.replace(/\[U\]([\s\S]*?)\[\/U\]/gi, '<u>$1</u>')
  html = html.replace(/\[S\]([\s\S]*?)\[\/S\]/gi, '<s>$1</s>')

  // Headings
  html = html.replace(/\[HEADING=1\]([\s\S]*?)\[\/HEADING\]/gi, '<h1>$1</h1>')
  html = html.replace(/\[HEADING=2\]([\s\S]*?)\[\/HEADING\]/gi, '<h2>$1</h2>')
  html = html.replace(/\[HEADING=3\]([\s\S]*?)\[\/HEADING\]/gi, '<h3>$1</h3>')

  // Quote
  html = html.replace(/\[QUOTE\]([\s\S]*?)\[\/QUOTE\]/gi, '<blockquote>$1</blockquote>')

  // Code
  html = html.replace(/\[CODE\]([\s\S]*?)\[\/CODE\]/gi, '<pre><code>$1</code></pre>')
  html = html.replace(/\[ICODE\]([\s\S]*?)\[\/ICODE\]/gi, '<code>$1</code>')

  // Lists
  html = html.replace(/\[LIST\]([\s\S]*?)\[\/LIST\]/gi, (_, inner) => {
    const items = inner.split(/\[\*\]/).filter(x => x.trim()).map(x => `<li>${x.trim().replace(/<br>/g, '')}</li>`).join('')
    return `<ul>${items}</ul>`
  })
  html = html.replace(/\[LIST=1\]([\s\S]*?)\[\/LIST\]/gi, (_, inner) => {
    const items = inner.split(/\[\*\]/).filter(x => x.trim()).map(x => `<li>${x.trim().replace(/<br>/g, '')}</li>`).join('')
    return `<ol>${items}</ol>`
  })

  // URL
  html = html.replace(/\[URL=([^\]]*)\]([\s\S]*?)\[\/URL\]/gi, '<a href="$1">$2</a>')
  html = html.replace(/\[URL\]([\s\S]*?)\[\/URL\]/gi, '<a href="$1">$1</a>')

  // IMG
  html = html.replace(/\[IMG\]([\s\S]*?)\[\/IMG\]/gi, '<img src="$1" />')

  // HR
  html = html.replace(/\[HR\]\[\/HR\]/gi, '<hr>')

  // Alignment
  html = html.replace(/\[CENTER\]([\s\S]*?)\[\/CENTER\]/gi, '<p style="text-align: center">$1</p>')
  html = html.replace(/\[RIGHT\]([\s\S]*?)\[\/RIGHT\]/gi, '<p style="text-align: right">$1</p>')

  return html
}


// ── Önizleme HTML (BB-Code → stillenmiş HTML) ────────────
export function bbCodeToPreviewHtml(bbcode) {
  let html = bbCodeToHtml(bbcode)

  // Stil ekle
  html = html.replace(/<h1>/g, '<h1 style="font-size:1.75rem;font-weight:700;margin:1rem 0 0.5rem;">')
  html = html.replace(/<h2>/g, '<h2 style="font-size:1.5rem;font-weight:700;margin:0.75rem 0;">')
  html = html.replace(/<h3>/g, '<h3 style="font-size:1.25rem;font-weight:600;margin:0.5rem 0;">')
  html = html.replace(/<blockquote>/g, '<blockquote style="border-left:3px solid #6366f1;padding:0.5rem 1rem;margin:0.5rem 0;color:#9ca3af;">')
  html = html.replace(/<pre><code>/g, '<pre style="background:#1e293b;padding:1rem;border-radius:8px;overflow-x:auto;"><code style="font-size:0.85em;">')
  html = html.replace(/<code>/g, '<code style="background:#1e293b;padding:2px 6px;border-radius:4px;font-size:0.85em;">')
  html = html.replace(/<a /g, '<a style="color:#818cf8;text-decoration:underline;" ')
  html = html.replace(/<img /g, '<img style="max-width:100%;border-radius:8px;margin:0.5rem 0;" ')
  html = html.replace(/<ul>/g, '<ul style="padding-left:1.5rem;margin:0.5rem 0;">')
  html = html.replace(/<ol>/g, '<ol style="padding-left:1.5rem;margin:0.5rem 0;">')

  return html
}
