import{k as a,l as e,F as g,B as u,g as i,t as l,x as d,A as m,m as c,w as b,T as v,r as z}from"./vendor-B5MtvwQk.js";import{_ as p}from"./_plugin-vue_export-helper-DlAUqK2U.js";const f={class:"max-w-screen-lg mx-auto space-y-5 animate-fade-in"},x={class:"card p-5"},S={class:"flex items-center justify-center gap-2 flex-wrap py-2"},h={class:"flow-step"},_={class:"text-xl"},G={class:"text-xs font-medium text-gray-200"},B={class:"text-[10px] text-gray-500"},Y={key:0,class:"text-gray-600 text-lg"},A={class:"space-y-2"},T=["onClick"],F={class:"text-lg"},K={class:"text-sm font-medium text-gray-200 flex-1"},C=["innerHTML"],I={__name:"GuideView",setup(E){const r=z("overview"),y=[{id:"overview",icon:"🏠",title:"Panel Nedir?",content:"Bilge Yolcu Kontrol Paneli, bilgeyolcu.com platformu için geliştirilmiş yapay zeka destekli bir içerik yönetim sistemidir. Felsefe, bilim, kültür ve düşünce tarihi üzerine özgün makaleler üretmek, düzenlemek ve XenForo forumuna yayınlamak için tasarlanmıştır."},{id:"workflow",icon:"🔄",title:"İş Akışı",content:`İçerik üretim süreci 4 adımdan oluşur:

1. <strong>Konu Belirle</strong> — Görev Kuyruğu'ndan AI makale görevi oluştur. Konu, ton, uzunluk ve parametreleri seç.

2. <strong>AI Üretir</strong> — Yapay zeka belirlenen parametrelere göre makaleyi yazar. Bu süreçte bütçe kontrolü yapılır.

3. <strong>Düzenle</strong> — Tamamlanan görevi "Yayına Gönder" ile Yayın Kuyruğu'na aktar. TipTap editörle düzenle, AI araçlarıyla genişlet.

4. <strong>Yayınla</strong> — Hedef forumu seç ve "XenForo'ya Yayınla" ile konu oluştur.`},{id:"tasks",icon:"⚡",title:"Görev Kuyruğu",content:`Görev Kuyruğu, AI içerik üretim görevlerini yönettiğiniz yerdir.

<strong>Görev Oluşturma:</strong> Konu, yazım stili (24 farklı ton), uzunluk hedefi ve ek notlarla görev başlatın.

<strong>Görev İzleme:</strong> Görevler sırasıyla PENDING → RUNNING → SUCCESS/FAILED durumlarından geçer. Tablodaki herhangi bir satıra tıklayarak detay modalını açabilirsiniz.

<strong>Aksiyonlar:</strong> Başarılı görevleri "Yayına Gönder", başarısız olanları "Tekrar Dene" veya "Sil" ile yönetin.`},{id:"publish",icon:"📝",title:"Yayın Kuyruğu & Editör",content:`Yayın Kuyruğu, içerikleri son hallerine getirip XenForo'ya yayınladığınız alandır.

<strong>Editör Modları:</strong>
• <strong>✏️ Editör</strong> — WYSIWYG (Word benzeri) görsel düzenleme
• <strong>📝 BB-Code</strong> — Ham BB-Code metin editörü (gelişmiş kullanıcılar)
• <strong>👁 Önizleme</strong> — İçeriğin yayınlanmış halinin körizlemesi

<strong>AI Araçları (✨ butonu):</strong>
• Genişlet — Seçili paragrafı detaylandır
• Yeniden Yaz — Farklı ifadelerle yeniden oluştur
• Daha Uzun Yap — Tüm makaleyi genişlet
• Özetle — Kısalt
• Devam Et — Metnin devamını yazdır
• Çevir — İngilizce metni Türkçeye çevir

<strong>Yazım Stilleri:</strong> 24 farklı ton seçeneği ile AI'ın üslubunu belirleyebilirsiniz (Felsefi, Bilimsel, Anlatı, Yaratıcı, Haber ve daha fazlası).`},{id:"budget",icon:"◎",title:"Bütçe Yönetimi",content:`Bütçe sayfası, AI API kullanımınıza ilişkin maliyetleri takip eder.

<strong>Günlük Limit:</strong> Her gün belirlenen bütçe sınırı içinde çalışır. Limit aşılırsa yeni görev başlatılamaz.

<strong>Model Maliyetleri:</strong> Gemini, Claude ve GPT modellerinin token başına maliyet karşılaştırması gösterilir.

<strong>Maliyet Grafiği:</strong> Günlük/haftalık harcama trendlerinizi analiz edin.`},{id:"xenforo",icon:"🏛",title:"XenForo",content:`XenForo sayfası, forum yönetim arayüzüdür.

<strong>Forum Listesi:</strong> XenForo node'larını (forum bölümleri) görüntüleyin.
<strong>Konu Yönetimi:</strong> Son konuları listeleyin, detayları görüntüleyin.
<strong>API Durumu:</strong> XenForo API bağlantı sağlığını kontrol edin.`},{id:"devops",icon:"🖥",title:"Sistem & Tema",content:`Bu sayfa 4 sekme içerir:

<strong>📊 Sistem Durumu:</strong> SSH bağlantı durumu, disk kullanımı, bellek, PHP ve XenForo sürümleri.

<strong>⌨️ SSH Terminal:</strong> Sunucuya doğrudan komut gönderin. Hızlı komut butonlarıyla sık kullanılan işlemlere erişin (disk, bellek, süreçler vb.).

<strong>🚀 XF Güncelleyici:</strong> XenForo sürüm güncelleme pipeline'ı. Otomatik yedek → bakım modu → upgrade → açık.

<strong>🎨 Tema Editörü:</strong> XenForo tema dosyalarını (LESS, CSS, HTML) SSH üzerinden düzenleyin. Monaco editör ile syntax highlighting.`},{id:"tones",icon:"🎨",title:"Yazım Stilleri",content:`24 farklı yazım stili mevcuttur:

🔮 <strong>Felsefi</strong> — Spekülatif, soru soran
🔬 <strong>Bilimsel</strong> — Kanıt odaklı, akademik
📖 <strong>Anlatı</strong> — Hikâye kurar gibi, edebi
🔍 <strong>SEO</strong> — Arama motoru uyumlu
💡 <strong>Yaratıcı</strong> — Beklenmedik bakış açıları
📰 <strong>Haber</strong> — 5N1K, nesnel
🎓 <strong>Eğitici</strong> — Adım adım, öğretici
💬 <strong>Sohbet</strong> — Blog tarzı, samimi
⚔️ <strong>Polemik</strong> — Tartışmacı, tez-antitez
🌟 <strong>İlham Verici</strong> — Motivasyonel
🎭 <strong>Satirik</strong> — İronik, eleştirel
⚖️ <strong>Karşılaştırma</strong> — Analiz, fark-benzerlik
🏛️ <strong>Tarihsel</strong> — Kronolojik, dönem analizi
🛠️ <strong>Teknik</strong> — Nasıl yapılır rehberi
🧠 <strong>Psikolojik</strong> — Davranış bilimi
🚀 <strong>Spekülatif</strong> — Gelecek tahminleri
✂️ <strong>Minimalist</strong> — Kısa ve çarpıcı
📋 <strong>Akademik</strong> — Tez formatı, atıf stili
🔎 <strong>Eleştirel</strong> — Eser/film incelemesi
✉️ <strong>Mektup</strong> — Okuyucuya hitap
📣 <strong>Manifesto</strong> — Güçlü çağrı, ideolojik
🎙️ <strong>Diyalog</strong> — Söyleşi formatı
🐉 <strong>Mitolojik</strong> — Sembol ve arketip analizi
✍️ <strong>Deneme</strong> — Serbest düşünce akışı`},{id:"faq",icon:"❓",title:"Sıkça Sorulan Sorular",content:`<strong>S: Görev başarısız olursa ne yapmalıyım?</strong>
C: Görev satırına tıklayıp hata detayını görün. "Tekrar Dene" ile yeniden başlatabilirsiniz. Bütçe doluysa ertesi güne bekleyin.

<strong>S: Makale çok kısa geldi, ne yapabilirim?</strong>
C: Yayın Kuyruğu'nda AI "Daha Uzun Yap" aracını kullanın veya yeni görev oluştururken "uzun" veya "çok_uzun" seçeneğini seçin.

<strong>S: XenForo'ya yayınlanan yazının formatı bozuk mu?</strong>
C: Editör otomatik olarak BB-Code'a dönüştürür. Eğer sorun varsa BB-Code moduna geçerek manuel düzeltme yapabilirsiniz.

<strong>S: Bütçem doldu, ne olur?</strong>
C: Günlük limit sıfırlanana kadar yeni AI görevi başlatılamaz. Mevcut taslaklar üzerinde çalışmaya devam edebilirsiniz.

<strong>S: SSH bağlantısı neden gerekli?</strong>
C: Tema editörü ve XF güncelleme işlemleri doğrudan sunucuya SSH bağlantısı üzerinden yapılır. SSH olmadan bu özellikler kullanılamaz.`}];function k(o){r.value=r.value===o?"":o}return(o,t)=>(i(),a("div",f,[t[1]||(t[1]=e("div",null,[e("h1",{class:"text-xl font-bold text-gray-100"},"❓ Kullanım Rehberi"),e("p",{class:"text-sm text-gray-500 mt-0.5"}," Bilge Yolcu Kontrol Paneli'nin nasıl kullanılacağını öğrenin ")],-1)),e("div",x,[t[0]||(t[0]=e("h2",{class:"text-sm font-semibold text-gray-300 mb-3"},"📋 Genel İş Akışı",-1)),e("div",S,[(i(),a(g,null,u([{icon:"⚡",label:"Görev Oluştur",sub:"Konu + Ton + Uzunluk"},{icon:"🤖",label:"AI Üretir",sub:"Gemini / Claude / GPT"},{icon:"📝",label:"Yayın Kuyruğu",sub:"Düzenle + İyileştir"},{icon:"🚀",label:"XenForo'ya Yayınla",sub:"Forum + Etiketler"}],(n,s)=>e("div",{key:s,class:"flex items-center gap-2"},[e("div",h,[e("span",_,l(n.icon),1),e("span",G,l(n.label),1),e("span",B,l(n.sub),1)]),s<3?(i(),a("span",Y,"→")):d("",!0)])),64))])]),e("div",A,[(i(),a(g,null,u(y,n=>e("div",{key:n.id,class:"card overflow-hidden"},[e("button",{onClick:s=>k(n.id),class:m(["w-full flex items-center gap-3 px-5 py-4 text-left transition-all",r.value===n.id?"bg-indigo-500/5":"hover:bg-gray-700/20"])},[e("span",F,l(n.icon),1),e("span",K,l(n.title),1),e("span",{class:m(["text-gray-500 text-xs transition-transform duration-200",r.value===n.id?"rotate-180":""])},"▼",2)],10,T),c(v,{name:"accordion"},{default:b(()=>[r.value===n.id?(i(),a("div",{key:0,class:"px-5 pb-5 text-sm text-gray-400 leading-relaxed guide-content",innerHTML:n.content},null,8,C)):d("",!0)]),_:2},1024)])),64))]),t[2]||(t[2]=e("div",{class:"text-center text-xs text-gray-700 py-4"}," Bilge Yolcu Kontrol Paneli — v2.0.0 ",-1))]))}},D=p(I,[["__scopeId","data-v-414dc44a"]]);export{D as default};
