/* Sprite Atölye — v0.1
   Ücretsiz oyun asset üretici: Pollinations ile üretim, tarayıcıda işleme.
   Motorlar ENGINES içinde; ileride Modal (kendi GPU motorumuz) buraya eklenecek. */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------------- Genel yardımcılar ---------------- */
function toast(msg, ms = 2600) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('on');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('on'), ms);
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

function newCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, w | 0);
  c.height = Math.max(1, h | 0);
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.imageSmoothingEnabled = false;
  return c;
}
function cloneCanvas(src) {
  const c = newCanvas(src.width, src.height);
  c.getContext('2d').drawImage(src, 0, 0);
  return c;
}
function showScaled(canvas, maxPx = 480) {
  const m = Math.max(canvas.width, canvas.height);
  const scale = m >= maxPx ? maxPx / m : Math.max(1, Math.floor(maxPx / m));
  canvas.style.width = Math.round(canvas.width * scale) + 'px';
  canvas.style.height = 'auto';
}
function canvasToBlob(c) {
  return new Promise(r => c.toBlob(r, 'image/png'));
}
function downloadBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
}
async function blobToCanvas(blob) {
  const bmp = await createImageBitmap(blob);
  const c = newCanvas(bmp.width, bmp.height);
  c.getContext('2d').drawImage(bmp, 0, 0);
  bmp.close && bmp.close();
  return c;
}
function slug(s) {
  return (s || 'sprite').toLowerCase()
    .replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ş/g, 's').replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ç/g, 'c')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'sprite';
}

/* ---------------- Sekmeler ---------------- */
function openTab(id) {
  $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === id));
  $$('.tab').forEach(s => s.classList.toggle('on', s.id === id));
  if (id === 'galeri') renderGallery();
  window.scrollTo(0, 0);
}
$$('#tabs button').forEach(b => b.onclick = () => openTab(b.dataset.tab));

/* ---------------- Galeri (IndexedDB) ---------------- */
const DB = {
  db: null,
  open() {
    if (this.db) return Promise.resolve(this.db);
    return new Promise((res, rej) => {
      const r = indexedDB.open('sprite-atolye', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('items', { keyPath: 'id', autoIncrement: true });
      r.onsuccess = () => { this.db = r.result; res(this.db); };
      r.onerror = () => rej(r.error);
    });
  },
  async tx(mode, fn) {
    const db = await this.open();
    return new Promise((res, rej) => {
      const t = db.transaction('items', mode);
      const st = t.objectStore('items');
      const out = fn(st);
      t.oncomplete = () => res(out && out.result !== undefined ? out.result : out);
      t.onerror = () => rej(t.error);
    });
  },
  add(item) { return this.tx('readwrite', s => s.add(item)); },
  del(id) { return this.tx('readwrite', s => s.delete(id)); },
  all() { return this.tx('readonly', s => s.getAll()); },
};
async function saveToGallery(canvas, name, tags = '') {
  const blob = await canvasToBlob(canvas);
  await DB.add({ name: name || 'sprite', tags, blob, w: canvas.width, h: canvas.height, t: Date.now() });
}

let galleryURLs = [];
async function renderGallery() {
  const list = $('#galeriListe');
  galleryURLs.forEach(u => URL.revokeObjectURL(u));
  galleryURLs = [];
  const q = $('#galeriAra').value.trim().toLowerCase();
  const items = (await DB.all()).filter(i => !q || (i.name + ' ' + i.tags).toLowerCase().includes(q)).reverse();
  list.innerHTML = items.length ? '' : '<p class="hint">Galeri boş. Üret ya da Atölye\'den kaydet.</p>';
  for (const it of items) {
    const url = URL.createObjectURL(it.blob);
    galleryURLs.push(url);
    const d = document.createElement('div');
    d.className = 'item';
    d.innerHTML = `<div class="img checker"><img src="${url}" alt=""></div>
      <div class="meta">${escapeHtml(it.name)} · ${it.w}×${it.h}</div>
      <div class="acts"><button data-a="at">Atölye</button><button data-a="in">İndir</button><button data-a="sil">Sil</button></div>`;
    d.querySelector('[data-a=at]').onclick = async () => { loadIntoWorkshop(await blobToCanvas(it.blob), it.name); openTab('atolye'); };
    d.querySelector('[data-a=in]').onclick = () => downloadBlob(it.blob, slug(it.name) + '.png');
    d.querySelector('[data-a=sil]').onclick = async () => { if (confirm('Silinsin mi?')) { await DB.del(it.id); renderGallery(); } };
    list.appendChild(d);
  }
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
$('#galeriAra').oninput = () => renderGallery();

/* Galeri seçici (tek ya da çoklu) */
function pickFromGallery(title, multi) {
  return new Promise(async resolve => {
    const dlg = $('#secici');
    $('#seciciBaslik').textContent = title;
    const box = $('#seciciListe');
    box.innerHTML = '';
    const items = (await DB.all()).reverse();
    if (!items.length) { toast('Galeri boş'); return resolve([]); }
    const chosen = [];
    const urls = [];
    for (const it of items) {
      const url = URL.createObjectURL(it.blob); urls.push(url);
      const d = document.createElement('div');
      d.className = 'item';
      d.innerHTML = `<div class="img checker"><img src="${url}" alt=""></div><div class="meta">${escapeHtml(it.name)}</div>`;
      d.onclick = () => {
        if (!multi) { chosen.length = 0; $$('.item', box).forEach(x => x.classList.remove('sel')); }
        const i = chosen.indexOf(it);
        if (i >= 0) { chosen.splice(i, 1); d.classList.remove('sel'); }
        else { chosen.push(it); d.classList.add('sel'); }
        if (multi) d.querySelector('.meta').textContent = (chosen.indexOf(it) + 1 || '') + ' ' + it.name;
      };
      box.appendChild(d);
    }
    const done = val => { dlg.close(); urls.forEach(u => URL.revokeObjectURL(u)); resolve(val); };
    $('#seciciTamam').onclick = () => done(chosen.slice());
    $('#seciciKapat').onclick = () => done([]);
    dlg.showModal();
  });
}

/* ---------------- Üretim motorları ---------------- */
const TUR = {
  karakter: 'solo, one single character alone, full body 2D game character, centered, whole body visible',
  dusman: 'solo, one single creature alone, full body 2D game enemy, centered, whole body visible',
  esya: 'single 2D game item asset, one object, centered',
  ikon: 'single game UI icon, simple readable shapes, centered',
  tile: 'seamless tileable game ground texture, pattern fills the entire image edge to edge',
  bina: 'single 2D game building or prop asset, one object, centered',
  ui: 'single game UI element (button, panel or bar), clean readable shapes, front view, centered',
  kart: 'ornate trading card frame border only, empty plain center, symmetrical, front view, game card template',
  serbest: '',
};
const STIL = {
  pixel: 'pixel art, crisp pixels, limited color palette, retro game sprite',
  cartoon: '2D cartoon game art, clean bold outlines, flat colors',
  hd: 'high quality 2D game art, hand painted, detailed shading',
  chibi: 'cute chibi style 2D game art, big head small body, clean outlines',
  dark: 'dark fantasy 2D game art, moody desaturated colors, strong outlines',
};
// Modal motorunda stile özel LoRA (motor bilmiyorsa yok sayar). pixel kendi LoRA'sını zaten kullanır.
// karanlık (arka planı koyulaştırıyor) ve HD (fark yok) için henüz açılmadı — 21 Kasım karşılaştırması
const LORA_STIL = { cartoon: 'cartoon', chibi: 'chibi' };
function loraFor(stil) {
  const k = document.getElementById('loraAc');
  return (!k || k.checked) ? LORA_STIL[stil] : undefined;
}
const BAKIS = {
  front: 'front view facing the camera',
  side: 'side view profile facing right',
  topdown: 'top-down view seen from directly above',
  iso: 'isometric view',
  threequarter: 'three-quarter view',
  back: 'back view seen from behind, facing away from the camera',
};
/* Arka plan rengi: karakterde geçen renklerle çakışmayan ilk renk (aynı renk kıyafet silinmesin) */
const BG_SECENEK = [
  ['medium gray', /\b(gray|grey|silver|gri|gümüş|gumus|steel|metal|ash)\b/i],
  ['white', /\b(white|beyaz|snow|kar|pale|ivory|cream)\b/i],
  ['light sky blue', /\b(blue|mavi|cyan|turquoise|turkuaz|sky|ice|buz|water|su)\b/i],
  ['pale pink', /\b(pink|pembe|rose|red|kırmızı|kirmizi)\b/i],
];
function pickBg(text) {
  for (const [renk, re] of BG_SECENEK) if (!re.test(text)) return renk;
  return 'medium gray';
}
const bgText = renk => `simple background, isolated on a plain flat solid ${renk} background, no environment, no shadow, no ground, no scenery`;

const trCache = new Map();
const TUR_EN = { karakter: 'game character', dusman: 'game enemy creature', esya: 'game item', ikon: 'game icon', tile: 'ground texture', bina: 'game building or prop', ui: 'game UI element', kart: 'trading card frame', serbest: 'image' };
/* Tarif yorumlayıcı: serbest Türkçe tarifi modelin çizebileceği somut İngilizce özelliklere çevirir */
/* Otomatik tür/bakış — yapay zekâ cevap vermezse kelimelere bakarak */
function guessTur(t) {
  t = t.toLocaleLowerCase('tr');
  if (/(zemin|doku|döşeme|tile|çimen|toprak|parke|duvar dokusu)/.test(t)) return 'tile';
  if (/(kart çerçeve|çerçeve|kart şablon)/.test(t)) return 'kart';
  if (/(buton|düğme|panel|menü|can barı|arayüz|ui\b)/.test(t)) return 'ui';
  if (/(ikon|simge|icon)/.test(t)) return 'ikon';
  if (/(kılıç|kalkan|iksir|balta|mızrak|yay\b|ok\b|asa|tabanca|tüfek|sandık|anahtar|altın|para|mücevher|yüzük|kitap|eşya|silah|zırh parçası)/.test(t)) return 'esya';
  if (/(ev\b|kale|kule|bina|ağaç|kaya|çit|köprü|çadır|tapınak|dükkan)/.test(t)) return 'bina';
  if (/(canavar|yaratık|zombi|örümcek|ejderha|iskelet|hayalet|goblin|ork|slime|balçık|kurt|yılan|böcek|şeytan|iblis|düşman|vampir|mumya|golem)/.test(t)) return 'dusman';
  return 'karakter';
}
function guessBakis(t, tur) {
  t = t.toLocaleLowerCase('tr');
  if (tur === 'tile') return 'topdown';
  if (tur === 'ui' || tur === 'kart' || tur === 'ikon' || tur === 'esya') return 'front';
  if (/(örümcek|yılan|solucan|böcek|at\b|köpek|kedi\b|kurt|araba|gemi|tank)/.test(t)) return 'side';
  if (tur === 'bina') return 'threequarter';
  return 'front';
}
const TURLER = ['karakter', 'dusman', 'esya', 'ikon', 'tile', 'bina', 'ui', 'kart'];
const BAKISLAR = ['front', 'side', 'topdown', 'iso', 'threequarter'];
const TUR_TR = { karakter: 'Karakter', dusman: 'Düşman', esya: 'Eşya', ikon: 'İkon', tile: 'Zemin', bina: 'Bina/Obje', ui: 'Arayüz', kart: 'Kart çerçevesi' };
const BAKIS_TR = { front: 'Önden', side: 'Yandan', topdown: 'Tepeden', iso: 'İzometrik', threequarter: '3/4', back: 'Arkadan' };

async function interpret(text, tur, cins, bakis = 'front') {
  if (!text.trim()) return { en: text, tur, bakis };
  const auto = tur === 'auto' || bakis === 'auto';
  const key = [text, tur, cins, bakis].join('|');
  if (trCache.has(key)) return trCache.get(key);
  const g = cins === 'erkek' ? 'The character is male (a man or boy). '
    : cins === 'kadin' ? 'The character is female (a woman or girl). ' : '';
  const head = auto
    ? 'First line must be exactly: TYPE=<one of: character, enemy, item, icon, tile, building, ui, cardframe>; VIEW=<one of: front, side, topdown, iso, threequarter>. ' +
      'enemy = monsters, creatures, undead, beasts; character = heroes, people, NPCs; item = weapons, potions, objects; tile = ground textures; building = houses, trees, props. ' +
      'VIEW: side for animals with many legs, snakes, vehicles; topdown for tiles; front for most characters. Then on the second line write the description. '
    : '';
  const q = `You write prompts for an image model that draws 2D game assets. Convert this Turkish description of a ${tur === 'auto' ? 'game asset' : (TUR_EN[tur] || 'game asset')} into a concise English visual description. ` + head +
    'Rules: describe only what can be seen (gender, age, body build, face and expression, hair, skin, clothing with colors, accessories, held items, pose). ' +
    'Turn abstract traits into visible details (strong -> muscular arms and broad shoulders; capable -> confident stance with a tool belt; slightly tired -> faint dark circles under the eyes; happy -> warm smile). ' +
    'Start with the overall body plan and creature type first (e.g. "spider-bodied creature with a cat head", "winged lion humanoid"), because the image model weighs the first words most; if the body is not humanoid say so explicitly (e.g. "not humanoid, no arms"). ' +
    'For hybrid creatures say exactly which body part comes from which animal and what is missing (e.g. "long snake body with no legs and no arms, coiled tail, monkey head"), so the body type is not lost. ' +
    'Keep every concrete detail that is given, never drop one. ' + g +
    'Do not mention background, art style, lighting or camera. Reply with one line of comma-separated phrases, at most 50 words. ' +
    'ONLY if it is a hybrid of different animals/beings, add one more final line exactly like: PARTS=head:monkey head with red eyes and fangs;wings:bat wings|BASE=snake|NO=legs,arms ' +
    '(NO = body parts that must NOT exist, e.g. legs for a snake body; write NO= empty if none) ' +
    '(parts are simple English body-part nouns taken from the NON-base animal; BASE is the animal of the main body). No other text.\n\nDescription: ' + text;
  try {
    const ac = new AbortController();
    const to = setTimeout(() => ac.abort(), 20000);
    const r = await fetch('https://text.pollinations.ai/' + encodeURIComponent(q), { signal: ac.signal });
    clearTimeout(to);
    if (r.ok) {
      let raw = (await r.text()).trim();
      let rt = tur, rb = bakis, parts = null, base = '', absent = [];
      const pm = raw.match(/PARTS\s*=\s*([^|\n]*)\|\s*BASE\s*=\s*([^|\n]+)(?:\|\s*NO\s*=\s*([^\n]*))?/i);
      if (pm) {
        parts = pm[1].split(';').map(x => { const i = x.indexOf(':'); return i > 0 ? { name: x.slice(0, i).trim(), want: x.slice(i + 1).trim() } : null; }).filter(p => p && p.name && p.want).slice(0, 3);
        base = pm[2].trim().replace(/[.\s]+$/, '');
        absent = (pm[3] || '').split(/[,;]/).map(x => x.trim().replace(/[.]+$/, '')).filter(x => x && !/^(none|empty|-)$/i.test(x)).slice(0, 3);
        raw = raw.replace(pm[0], '');
      }
      const m = raw.match(/TYPE\s*=\s*(\w+)\s*;?\s*VIEW\s*=\s*(\w+)/i);
      if (m) {
        const tmap = { character: 'karakter', enemy: 'dusman', item: 'esya', icon: 'ikon', tile: 'tile', building: 'bina', ui: 'ui', cardframe: 'kart' };
        if (tur === 'auto') rt = tmap[m[1].toLowerCase()] || guessTur(text);
        if (bakis === 'auto' && BAKISLAR.includes(m[2].toLowerCase())) rb = m[2].toLowerCase();
        raw = raw.replace(m[0], '');
      }
      let out = raw.replace(/^[\s.;:-]+/, '').replace(/^["'`]+|["'`]+$/g, '').replace(/\s+/g, ' ').trim();
      if (out && out.length < 600 && !/^(sorry|i can)/i.test(out)) {
        if (rt === 'auto') rt = guessTur(text);
        if (rb === 'auto') rb = guessBakis(text, rt);
        const res = { en: out, tur: rt, bakis: rb, parts: parts && parts.length ? parts : null, base, absent: absent.length ? absent : null };
        trCache.set(key, res); return res;
      }
    }
  } catch (e) { /* olmazsa sözlük kullanılır */ }
  const rt = tur === 'auto' ? guessTur(text) : tur;
  const rb = bakis === 'auto' ? guessBakis(text, rt) : bakis;
  const fb = dictTranslate(text);
  return { en: (cins === 'erkek' ? 'man, ' : cins === 'kadin' ? 'woman, ' : '') + fb, tur: rt, bakis: rb };
}
async function toEnglish(text) { return (await interpret(text, 'serbest', '')).en; }

/* Yedek: oyun asset'lerinde sık geçen Türkçe kelimeler */
const SOZLUK = {
  kedi: 'cat', köpek: 'dog', kopek: 'dog', kurt: 'wolf', ayı: 'bear', tavşan: 'rabbit', fare: 'mouse', kuş: 'bird', at: 'horse',
  ejderha: 'dragon', yılan: 'snake', örümcek: 'spider', iskelet: 'skeleton', zombi: 'zombie', hayalet: 'ghost', goblin: 'goblin', ork: 'orc',
  şövalye: 'knight', asker: 'soldier', büyücü: 'wizard', cadı: 'witch', okçu: 'archer', savaşçı: 'warrior', ninja: 'ninja', korsan: 'pirate',
  kral: 'king', kraliçe: 'queen', prenses: 'princess', robot: 'robot', uzaylı: 'alien', canavar: 'monster', slime: 'slime', balçık: 'slime',
  kılıç: 'sword', kalkan: 'shield', yay: 'bow', ok: 'arrow', balta: 'axe', mızrak: 'spear', asa: 'magic staff', tabanca: 'pistol', tüfek: 'rifle',
  iksir: 'potion', sandık: 'treasure chest', altın: 'gold', para: 'coin', mücevher: 'gem', anahtar: 'key', kalp: 'heart', yıldız: 'star',
  ev: 'house', kale: 'castle', kule: 'tower', ağaç: 'tree', kaya: 'rock', çimen: 'grass', taş: 'stone', su: 'water', lav: 'lava', kum: 'sand', kar: 'snow',
  kırmızı: 'red', mavi: 'blue', yeşil: 'green', sarı: 'yellow', siyah: 'black', beyaz: 'white', mor: 'purple', turuncu: 'orange', pembe: 'pink', kahverengi: 'brown', gri: 'gray',
  küçük: 'small', büyük: 'big', sevimli: 'cute', korkunç: 'scary', yaşlı: 'old', genç: 'young', kızgın: 'angry', mutlu: 'happy', koşan: 'running', uçan: 'flying',
  papyon: 'bow tie', şapka: 'hat', gözlük: 'glasses', pelerin: 'cape', zırh: 'armor', miğfer: 'helmet', taç: 'crown', elbise: 'dress', ceket: 'jacket', gömlek: 'shirt', çizme: 'boots',
};
const EKLER = ['lu', 'lü', 'li', 'lı'];
function dictTranslate(text) {
  const main = [], extra = [];
  for (const wd of text.split(/\s+/)) {
    const k = wd.toLocaleLowerCase('tr').replace(/[.,!?]/g, '');
    let done = false;
    for (const e of EKLER) if (k.endsWith(e) && SOZLUK[k.slice(0, -e.length)]) { extra.push('wearing ' + SOZLUK[k.slice(0, -e.length)]); done = true; break; }
    if (!done) main.push(SOZLUK[k] || wd);
  }
  return main.join(' ') + (extra.length ? ' ' + extra.join(', ') : '');
}

const PORTRE = ['karakter', 'dusman', 'kart'];
function sizeFor(tur, bakis) {
  if (tur === 'dusman' && (bakis === 'side' || bakis === 'topdown')) return { w: 1216, h: 832 }; // yatay yaratıklar (örümcek, yılan)
  return PORTRE.includes(tur) ? { w: 832, h: 1216 } : { w: 1024, h: 1024 };
}
function buildPrompt(desc, o) {
  const parts = [];
  if (o.stil === 'pixel' && o.tur !== 'serbest') parts.push('pixel art');
  parts.push(desc);
  if (o.tur !== 'serbest') {
    parts.push(TUR[o.tur], STIL[o.stil]);
    if (o.tur !== 'tile') parts.push(BAKIS[o.bakis], bgText(pickBg(desc + ' ' + (o.ham || ''))));
    else parts.push('top-down, even flat lighting, no shadows, no objects cut at edges');
  }
  if (o.recete) parts.push(o.recete);
  if (o.negatif) parts.push('without ' + o.negatif);
  return parts.filter(Boolean).join(', ');
}

const ENGINES = {
  pollinations: {
    name: 'Pollinations',
    minGap: 16000,
    async generate({ prompt, seed, model, w = 1024, h = 1024, seffaf = false, stil = '' }) {
      const url = 'https://image.pollinations.ai/prompt/' + encodeURIComponent(prompt) +
        `?width=${w}&height=${h}&seed=${seed}&model=${model}&nologo=true&private=true`;
      const ac = new AbortController();
      const to = setTimeout(() => ac.abort(), 150000);
      try {
        const r = await fetch(url, { signal: ac.signal });
        if (r.status === 429) { const e = new Error('Sıra dolu (429)'); e.retry = true; throw e; }
        if (!r.ok) throw new Error('Sunucu hatası ' + r.status);
        const blob = await r.blob();
        if (!blob.type.startsWith('image')) throw new Error('Görsel gelmedi');
        const c = await blobToCanvas(blob);
        if (!seffaf) return c;
        removeBackground(c, 45);
        const t = trimCanvas(c, 2);
        return stil === 'pixel' ? pixelate(t, 96, 0, false) : t;
      } finally { clearTimeout(to); }
    },
  },
  modal: {
    name: 'Modal (kendi GPU)',
    minGap: 0,
    async generate({ prompt, seed, stil, negatif, w = 1024, h = 1024, seffaf = false, ref = null, refScale = 0.6, tile = false, parts = null, base = '', absent = null, styleText = '' }) {
      const { url, key } = modalCfg();
      const ac = new AbortController();
      const to = setTimeout(() => ac.abort(), 300000);
      try {
        const r = await fetch(url.replace(/\/+$/, '') + '/generate', {
          method: 'POST', signal: ac.signal,
          headers: { 'Content-Type': 'application/json', 'X-Sprite-Key': key },
          body: JSON.stringify({ prompt, seed, n: 1, width: w, height: h, auto: seffaf, style: stil === 'pixel' ? 'pixel' : 'other', negative: negatif || undefined,
            reference: ref || undefined, ref_scale: refScale, tileable: tile,
            parts: parts || undefined, base, absent: absent || undefined, style_text: styleText, lora: loraFor(stil) }),
        });
        if (r.status === 401) throw new Error('Motor anahtarı yanlış');
        if (!r.ok) throw new Error('Modal hatası ' + r.status);
        const d = await r.json();
        if (d.plain && d.plain[0] === false) toast('Model desenli/çerçeveli arka plan çizdi; tam resim olarak verildi. Atölye\'de "Otomatik temizle" ya da yeniden üret.', 5000);
        const bin = Uint8Array.from(atob(d.images[0]), ch => ch.charCodeAt(0));
        const c = await blobToCanvas(new Blob([bin], { type: 'image/png' }));
        c._fixes = (d.fixes && d.fixes[0]) || null;
        c._dersler = d.dersler || [];
        c._ikiAsama = !!d.iki_asama;
        return c;
      } finally { clearTimeout(to); }
    },
  },
};
const PARCA_TR = { 'bütün': 'görsel', head: 'kafa', face: 'yüz', wings: 'kanat', wing: 'kanat', tail: 'kuyruk', arms: 'kollar', arm: 'kol', legs: 'bacaklar', body: 'gövde', horns: 'boynuz', hands: 'eller' };
function dersOzeti(c) {
  // motorun geçmiş hatalardan öğrendiği kurallar (modal/app.py DERSLER)
  if (!c || !c._dersler || !c._dersler.length) return '';
  return ' · dersler: ' + c._dersler.join(', ') + (c._ikiAsama ? ' (taslak→pixel)' : '');
}
function duzeltmeOzeti(f) {
  if (!f || !f.length) return '';
  return ' · oto-kontrol: ' + f.map(x => x.parca === 'taslak' ? `4 taslaktan en iyisi (${Math.round((x.skor || 0) * 100)}%)` : x.parca === 'sonuç' ? `tarife uygun ✓ (${Math.round((x.skor || 0) * 100)}%)` : x.hata ? 'hata' : `${PARCA_TR[x.parca] || x.parca} ${({ 'tuttu': '✓', 'düzeltildi': '✓ düzeltildi', 'bulunamadı': '?', 'yok ✓': 'yok ✓', 'silindi': 'silindi ✓', 'silinemedi': 'silinemedi ✗', 'cilalandı': 'cilalandı ✓', 'tarife uygun': 'tarife uygun ✓' })[x.durum] || '✗ zayıf'}`).join(', ');
}
const DEFAULT_MODAL_URL = 'https://malisah61--sprite-atolye-motor-web.us-east.modal.run';
function modalCfg() {
  return {
    url: (localStorage.getItem('sa-modal-url') || DEFAULT_MODAL_URL).trim(),
    key: (localStorage.getItem('sa-modal-key') || '').trim(),
  };
}
function pickEngine() {
  const m = localStorage.getItem('sa-motor') || 'auto';
  const { url } = modalCfg();
  if (m === 'pollinations' || !url) return ENGINES.pollinations;
  return ENGINES.modal;
}
let engine = pickEngine();
$('#motorSec').value = localStorage.getItem('sa-motor') || 'auto';
$('#modalUrl').value = modalCfg().url;
$('#modalKey').value = modalCfg().key;
function saveMotor() {
  localStorage.setItem('sa-motor', $('#motorSec').value);
  localStorage.setItem('sa-modal-url', $('#modalUrl').value.trim());
  localStorage.setItem('sa-modal-key', $('#modalKey').value.trim());
  engine = pickEngine();
  $('#durum').textContent = 'Motor: ' + engine.name;
}
['#motorSec', '#modalUrl', '#modalKey'].forEach(s => $(s).onchange = saveMotor);
$('#btnMotorTest').onclick = async () => {
  saveMotor();
  const { url } = modalCfg();
  if (!url) return toast('Önce motor adresini yaz');
  toast('Motor uyandırılıyor, 1-2 dk sürebilir...', 5000);
  try {
    const r = await fetch(url.replace(/\/+$/, '') + '/');
    const d = await r.json();
    toast(d.ok ? 'Motor çalışıyor: ' + d.motor : 'Beklenmeyen cevap', 4000);
  } catch (e) { toast('Bağlanamadı: ' + e.message, 4000); }
};

/* Sıra: ücretsiz katmanda istekler arası bekleme */
const queue = [];
let lastStart = 0, running = false;
function enqueue(job) { queue.push(job); runQueue(); }
async function runQueue() {
  if (running) return;
  running = true;
  while (queue.length) {
    const job = queue.shift();
    const gap = (job.engine || engine).minGap;
    let wait = lastStart + gap - Date.now();
    while (wait > 0) {
      job.onWait(Math.ceil(wait / 1000));
      await sleep(Math.min(1000, wait));
      wait = lastStart + gap - Date.now();
    }
    const eng = job.engine || engine;
    job.onStart(eng);
    lastStart = Date.now();
    try {
      job.onDone(await eng.generate(job.params));
    } catch (e) {
      const auto = (localStorage.getItem('sa-motor') || 'auto') === 'auto';
      if (eng === ENGINES.modal && auto && !job.fellBack) {
        job.fellBack = true; job.engine = ENGINES.pollinations; queue.unshift(job);
        toast('Modal cevap vermedi, Pollinations\'a geçildi');
      } else if (e.retry && !job.retried) { job.retried = true; lastStart = Date.now() + 5000; queue.unshift(job); }
      else job.onError(e);
    }
  }
  running = false;
  $('#durum').textContent = 'Hazır. Motor: ' + engine.name + ' (ücretsiz).';
}

let lastDesc = '', lastYorum = '', lastTur = '', lastBakis = '', lastParts = null, lastBase = '', lastAbsent = null;
$('#tur').onchange = () => { $('#cinsKutu').hidden = !['auto', 'karakter', 'dusman'].includes($('#tur').value); };
$('#btnUret').onclick = async () => {
  const desc = $('#prompt').value.trim();
  if (!desc) return toast('Önce ne üretileceğini yaz');
  const o = {
    tur: $('#tur').value, stil: $('#stil').value, bakis: $('#bakis').value,
    recete: $('#recete').value.trim(), negatif: $('#negatif').value.trim(),
    seffaf: $('#seffaf').checked,
  };
  localStorage.setItem('sa-seffaf', $('#seffaf').checked ? '1' : '0');
  localStorage.setItem('sa-recete', o.recete);
  const n = +$('#adet').value;
  const model = $('#model').value;
  const seedIn = $('#seed').value;
  const baseSeed = seedIn ? +seedIn : Math.floor(Math.random() * 1e9);
  $('#durum').textContent = 'Hazırlanıyor...';
  const cins = $('#cins').value;
  let en;
  if ($('#ham').checked) {
    en = desc;
    if (o.tur === 'auto') o.tur = guessTur(desc);
    if (o.bakis === 'auto') o.bakis = guessBakis(desc, o.tur);
  } else if (desc === lastDesc && $('#yorum').value.trim() && $('#yorum').value.trim() !== lastYorum) {
    en = $('#yorum').value.trim(); // elle düzeltilmiş yorum
    o.parts = lastParts; o.base = lastBase; o.absent = lastAbsent;
    if (o.tur === 'auto') o.tur = lastTur || guessTur(desc);
    if (o.bakis === 'auto') o.bakis = lastBakis || guessBakis(desc, o.tur);
  } else {
    $('#durum').textContent = 'Tarif yorumlanıyor...';
    const r = await interpret(desc, o.tur, cins, o.bakis);
    en = r.en; o.tur = r.tur; o.bakis = r.bakis; o.parts = r.parts; o.base = r.base; o.absent = r.absent;
    lastParts = r.parts; lastBase = r.base; lastAbsent = r.absent;
  }
  lastTur = o.tur; lastBakis = o.bakis;
  if (o.tur === 'tile') o.seffaf = false;
  lastDesc = desc; lastYorum = en;
  $('#yorum').value = en;
  $('#yorumKutu').hidden = false;
  const ref = REF.b64 && engine === ENGINES.modal ? REF.b64 : null;
  if (REF.b64 && !ref) toast('Referans sadece Modal motorunda çalışır', 3000);
  $('#durum').textContent = `Üretiliyor... Tür: ${TUR_TR[o.tur] || o.tur} · Bakış: ${BAKIS_TR[o.bakis] || o.bakis}${ref ? ' · referanslı' : ''}`;
  for (let i = 0; i < n; i++) uretimKarti({ desc, en, o, seed: baseSeed + i, model, ref, refScale: REF.scale });
};

/* Tek üretim kartı (Üret ve Yön seti ortak kullanır) */
function uretimKarti({ desc, en, o, seed, model, ref = null, refScale = 0.6, etiket = '' }) {
  const prompt = buildPrompt(en, { ...o, ham: desc });
  const card = document.createElement('div');
  card.className = 'item';
  card.innerHTML = `<div class="img checker"><div class="wait">Sırada...</div></div><div class="meta" title="${escapeHtml(prompt)}">${escapeHtml(etiket ? etiket + ' · ' : '')}${escapeHtml(desc)} · seed ${seed}</div>`;
  $('#sonuclar').prepend(card);
  const w = card.querySelector('.wait');
  enqueue({
    params: { prompt, seed, model, stil: o.stil, negatif: o.negatif, seffaf: o.seffaf, ref, refScale, tile: o.tur === 'tile',
      parts: o.parts || null, base: o.base || '', absent: o.absent || null, styleText: STIL[o.stil] || '', ...sizeFor(o.tur, o.bakis) },
    onWait: s => { w.textContent = `Sırada · ${s} sn`; $('#durum').textContent = `Sıra: ${queue.length + 1} iş bekliyor`; },
    onStart: eng => { w.textContent = 'Üretiliyor (' + eng.name + ')...'; card.querySelector('.meta').textContent += ' · ' + eng.name.split(' ')[0]; },
    onDone: c => {
      const box = card.querySelector('.img');
      box.innerHTML = '';
      const view = cloneCanvas(c);
      showScaled(view, 150);
      box.appendChild(view);
      card.querySelector('.meta').textContent += ` · ${c.width}×${c.height}` + duzeltmeOzeti(c._fixes) + dersOzeti(c);
      const acts = document.createElement('div');
      acts.className = 'acts wrap';
      acts.innerHTML = '<button data-a="at">Atölye</button><button data-a="kay">Kaydet</button><button data-a="in">İndir</button>' +
        (['karakter', 'dusman'].includes(o.tur) ? '<button data-a="yon">Yön seti</button><button data-a="ref">Referans yap</button>' : '<button data-a="ref">Referans yap</button>');
      acts.querySelector('[data-a=at]').onclick = () => { loadIntoWorkshop(cloneCanvas(c), desc, en); openTab('atolye'); };
      acts.querySelector('[data-a=kay]').onclick = async () => { await saveToGallery(c, desc, prompt); toast('Galeriye kaydedildi'); };
      acts.querySelector('[data-a=in]').onclick = async () => downloadBlob(await canvasToBlob(c), slug(desc) + '-' + seed + '.png');
      acts.querySelector('[data-a=ref]').onclick = () => { referansAyarla(c); window.scrollTo(0, 0); };
      const yon = acts.querySelector('[data-a=yon]');
      if (yon) yon.onclick = () => yonSeti(c, { desc, en, o, seed, model });
      card.appendChild(acts);
    },
    onError: e => { w.textContent = 'Hata: ' + e.message + ' — tekrar dene'; },
  });
}

/* Yön seti: aynı karakteri önden, yandan, arkadan (referanslı) */
function yonSeti(c, { desc, en, o, seed, model }) {
  if (engine !== ENGINES.modal) return toast('Yön seti için Modal motoru gerekli');
  const ref = c.toDataURL('image/png').split(',')[1];
  [['front', 'Ön'], ['side', 'Yan'], ['back', 'Arka']].forEach(([b, ad]) => {
    const en2 = 'the exact same character, same outfit and colors, ' + en;
    uretimKarti({ desc, en: en2, o: { ...o, bakis: b }, seed, model, ref, refScale: 0.7, etiket: ad });
  });
  toast('Yön seti üretiliyor: ön, yan, arka', 3000);
}

/* Referans görsel (IP-Adapter): bu görsele benzeyen yeni üretimler */
const REF = { b64: null, scale: +(localStorage.getItem('sa-ref-scale') || 0.6) };
function referansAyarla(c) {
  if (!c) { REF.b64 = null; $('#refKutu').hidden = true; return; }
  const t = c.width * c.height > 1024 * 1024 ? (() => { const s = 1024 / Math.max(c.width, c.height); const k = newCanvas(c.width * s, c.height * s); k.getContext('2d').imageSmoothingEnabled = true; k.getContext('2d').drawImage(c, 0, 0, k.width, k.height); return k; })() : c;
  REF.b64 = t.toDataURL('image/png').split(',')[1];
  const v = $('#refOnizle'); v.width = t.width; v.height = t.height; v.getContext('2d').drawImage(t, 0, 0); showScaled(v, 64);
  $('#refKutu').hidden = false;
  toast('Referans ayarlandı: yeni üretimler buna benzeyecek', 3000);
}
$('#btnRefSec').onclick = async () => { const [it] = await pickFromGallery('Referans görsel seç', false); if (it) referansAyarla(await blobToCanvas(it.blob)); };
$('#btnRefTemizle').onclick = () => referansAyarla(null);
$('#refScale').value = REF.scale; $('#oRef').textContent = REF.scale;
$('#refScale').oninput = e => { REF.scale = +e.target.value; $('#oRef').textContent = REF.scale; localStorage.setItem('sa-ref-scale', REF.scale); };

/* Oyun stilleri: oyun başına kayıtlı reçete + stil (+ referans) */
const VARSAYILAN_STILLER = {
  'Efsane Kartlar': { stil: 'pixel', recete: 'mythological legendary hero, vivid saturated colors, detailed heroic pixel art' },
  'Zombi Savunma': { stil: 'pixel', recete: 'gritty post-apocalyptic survival game, muted greens and browns, clean readable silhouette' },
  'Komando': { stil: 'hd', recete: 'World War II era, realistic military details, muted olive and khaki tones, tactical game art' },
  'Kule Savunma': { stil: 'cartoon', recete: 'bright fantasy tower defense, cheerful colors, chunky readable shapes' },
  'Dünya Kutusu': { stil: 'pixel', recete: 'tiny cute world sandbox sim, simple pixel art, 16-bit palette' },
};
function stilleriOku() { try { return { ...VARSAYILAN_STILLER, ...JSON.parse(localStorage.getItem('sa-stiller') || '{}') }; } catch { return { ...VARSAYILAN_STILLER }; } }
function stilListesiCiz() {
  const sel = $('#oyunStil'), sec = localStorage.getItem('sa-oyun-stil') || '';
  sel.innerHTML = '<option value="">— Oyun stili yok —</option>' + Object.keys(stilleriOku()).map(k => `<option ${k === sec ? 'selected' : ''}>${escapeHtml(k)}</option>`).join('');
}
$('#oyunStil').onchange = async () => {
  const ad = $('#oyunStil').value; localStorage.setItem('sa-oyun-stil', ad);
  if (!ad) return;
  const st = stilleriOku()[ad];
  if (st.stil) $('#stil').value = st.stil;
  $('#recete').value = st.recete || '';
  localStorage.setItem('sa-recete', $('#recete').value);
  if (st.ref) { const c = await blobToCanvas(new Blob([Uint8Array.from(atob(st.ref), ch => ch.charCodeAt(0))], { type: 'image/png' })); referansAyarla(c); }
  toast(ad + ' stili seçildi');
};
$('#btnStilKaydet').onclick = () => {
  const ad = prompt('Stil adı (ör. oyunun adı):', $('#oyunStil').value || ''); if (!ad) return;
  const kayit = JSON.parse(localStorage.getItem('sa-stiller') || '{}');
  kayit[ad] = { stil: $('#stil').value, recete: $('#recete').value.trim(), ...(REF.b64 && REF.b64.length < 1500000 ? { ref: REF.b64 } : {}) };
  try { localStorage.setItem('sa-stiller', JSON.stringify(kayit)); } catch { delete kayit[ad].ref; localStorage.setItem('sa-stiller', JSON.stringify(kayit)); }
  localStorage.setItem('sa-oyun-stil', ad); stilListesiCiz(); toast('Stil kaydedildi: ' + ad);
};
stilListesiCiz();
$('#recete').value = localStorage.getItem('sa-recete') || '';
$('#seffaf').checked = localStorage.getItem('sa-seffaf') !== '0';
try {
  $('#loraAc').checked = localStorage.getItem('sa-lora') !== '0';
  $('#loraAc').addEventListener('change', () => { try { localStorage.setItem('sa-lora', $('#loraAc').checked ? '1' : '0'); } catch (e) { /* yok */ } });
} catch (e) { /* kutu yoksa */ }

/* ---------------- Atölye ---------------- */
const WS = { canvas: null, name: 'sprite', history: [], en: '' };
function loadIntoWorkshop(c, name, en = '') {
  WS.canvas = c;
  WS.en = en;
  WS.name = name || 'sprite';
  WS.history = [];
  drawWorkshop();
}
function pushHistory() {
  WS.history.push(cloneCanvas(WS.canvas));
  if (WS.history.length > 15) WS.history.shift();
}
function drawWorkshop() {
  const v = $('#cvAtolye');
  if (!WS.canvas) return;
  v.width = WS.canvas.width; v.height = WS.canvas.height;
  const ctx = v.getContext('2d'); ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, v.width, v.height);
  ctx.drawImage(WS.canvas, 0, 0);
  showScaled(v);
  const mk = $('#cvMaske');
  if (mk.width !== v.width || mk.height !== v.height) { mk.width = v.width; mk.height = v.height; }
  $('#atolyeBilgi').textContent = `${WS.name} · ${WS.canvas.width}×${WS.canvas.height} px`;
}
function needWS() { if (!WS.canvas) { toast('Önce bir görsel seç'); return false; } return true; }

$('#dosya').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  loadIntoWorkshop(await blobToCanvas(f), f.name.replace(/\.\w+$/, ''));
  e.target.value = '';
};
$('#btnGaleridenSec').onclick = async () => {
  const [it] = await pickFromGallery('Atölyeye görsel seç', false);
  if (it) loadIntoWorkshop(await blobToCanvas(it.blob), it.name);
};
$('#tol').oninput = e => $('#oTol').textContent = e.target.value;

/* Arka plan silme: kenarlardan başlayan taşma doldurma (flood fill) */
function removeBackground(c, tol) {
  const w = c.width, h = c.height;
  const ctx = c.getContext('2d');
  const id = ctx.getImageData(0, 0, w, h), d = id.data;
  // kenar piksellerinin medyan rengi = arka plan
  const rs = [], gs = [], bs = [];
  const sample = (x, y) => { const i = (y * w + x) * 4; if (d[i + 3] > 0) { rs.push(d[i]); gs.push(d[i + 1]); bs.push(d[i + 2]); } };
  for (let x = 0; x < w; x += 2) { sample(x, 0); sample(x, h - 1); }
  for (let y = 0; y < h; y += 2) { sample(0, y); sample(w - 1, y); }
  if (!rs.length) return 0;
  const med = a => a.sort((p, q) => p - q)[a.length >> 1];
  const br = med(rs), bg = med(gs), bb = med(bs);
  const dist = i => Math.sqrt((d[i] - br) ** 2 + (d[i + 1] - bg) ** 2 + (d[i + 2] - bb) ** 2);
  const seen = new Uint8Array(w * h);
  const stack = [];
  const orig = new Uint8ClampedArray(d);
  // komşudan komşuya yumuşak geçiş (degrade/vinyet arka planlar için)
  const near = (a, b) => Math.abs(orig[a] - orig[b]) + Math.abs(orig[a + 1] - orig[b + 1]) + Math.abs(orig[a + 2] - orig[b + 2]);
  const tryPush = (p, from) => {
    if (seen[p]) return;
    const i = p * 4;
    const ok = orig[i + 3] === 0 || dist(i) < tol ||
      (from >= 0 && near(i, from * 4) < tol * 0.3 && dist(i) < tol * 2.2);
    if (ok) { seen[p] = 1; stack.push(p); }
  };
  for (let x = 0; x < w; x++) { tryPush(x, -1); tryPush((h - 1) * w + x, -1); }
  for (let y = 0; y < h; y++) { tryPush(y * w, -1); tryPush(y * w + w - 1, -1); }
  let removed = 0;
  while (stack.length) {
    const p = stack.pop();
    d[p * 4 + 3] = 0; removed++;
    const x = p % w, y = (p / w) | 0;
    if (x > 0) tryPush(p - 1, p);
    if (x < w - 1) tryPush(p + 1, p);
    if (y > 0) tryPush(p - w, p);
    if (y < h - 1) tryPush(p + w, p);
  }
  // kenar yumuşatma: silinen alana komşu, arka plana yakın pikselleri yarı saydam yap
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
    const p = y * w + x, i = p * 4;
    if (seen[p] || d[i + 3] === 0) continue;
    if (seen[p - 1] || seen[p + 1] || seen[p - w] || seen[p + w]) {
      const k = dist(i) / (tol * 2);
      if (k < 1) d[i + 3] = Math.round(d[i + 3] * Math.max(0, k));
    }
  }
  ctx.putImageData(id, 0, 0);
  return removed / (w * h);
}

function trimCanvas(c, pad = 1) {
  const w = c.width, h = c.height;
  const d = c.getContext('2d').getImageData(0, 0, w, h).data;
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (d[(y * w + x) * 4 + 3] > 16) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  }
  if (x1 < 0) return c;
  x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
  x1 = Math.min(w - 1, x1 + pad); y1 = Math.min(h - 1, y1 + pad);
  const out = newCanvas(x1 - x0 + 1, y1 - y0 + 1);
  out.getContext('2d').drawImage(c, x0, y0, out.width, out.height, 0, 0, out.width, out.height);
  return out;
}

/* Pixel art: alfa ağırlıklı küçültme + k-means palet + kontur */
function pixelate(src, size, colors, outline, outlineHex) {
  const sw = src.width, sh = src.height;
  const s = size / Math.max(sw, sh);
  const tw = Math.max(1, Math.round(sw * s)), th = Math.max(1, Math.round(sh * s));
  const sd = src.getContext('2d').getImageData(0, 0, sw, sh).data;
  const pad = outline ? 1 : 0;
  const out = newCanvas(tw + pad * 2, th + pad * 2);
  const octx = out.getContext('2d');
  const od = octx.createImageData(out.width, out.height);
  const o = od.data;
  const W = out.width;
  for (let ty = 0; ty < th; ty++) {
    const sy0 = Math.floor(ty * sh / th), sy1 = Math.max(sy0 + 1, Math.floor((ty + 1) * sh / th));
    for (let tx = 0; tx < tw; tx++) {
      const sx0 = Math.floor(tx * sw / tw), sx1 = Math.max(sx0 + 1, Math.floor((tx + 1) * sw / tw));
      let r = 0, g = 0, b = 0, a = 0, n = 0;
      for (let y = sy0; y < sy1; y++) for (let x = sx0; x < sx1; x++) {
        const i = (y * sw + x) * 4, al = sd[i + 3];
        r += sd[i] * al; g += sd[i + 1] * al; b += sd[i + 2] * al; a += al; n++;
      }
      const j = ((ty + pad) * W + tx + pad) * 4;
      if (a / n >= 110) {
        o[j] = r / a; o[j + 1] = g / a; o[j + 2] = b / a; o[j + 3] = 255;
      }
    }
  }
  if (colors > 0) quantize(o, colors);
  if (outline) {
    const oc = hexToRgb(outlineHex);
    const H = out.height;
    const solid = p => o[p * 4 + 3] === 255;
    const mark = new Uint8Array(W * H);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const p = y * W + x;
      if (o[p * 4 + 3] === 255) continue;
      if ((x > 0 && solid(p - 1)) || (x < W - 1 && solid(p + 1)) || (y > 0 && solid(p - W)) || (y < H - 1 && solid(p + W))) mark[p] = 1;
    }
    for (let p = 0; p < W * H; p++) if (mark[p]) { const j = p * 4; o[j] = oc[0]; o[j + 1] = oc[1]; o[j + 2] = oc[2]; o[j + 3] = 255; }
  }
  octx.putImageData(od, 0, 0);
  return out;
}
function hexToRgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }

function quantize(o, k) {
  const px = [];
  for (let i = 0; i < o.length; i += 4) if (o[i + 3] === 255) px.push(i);
  if (px.length <= k) return;
  // k-means++ benzeri başlangıç
  const cents = [];
  const first = px[(Math.random() * px.length) | 0];
  cents.push([o[first], o[first + 1], o[first + 2]]);
  const dmin = new Float64Array(px.length).fill(Infinity);
  while (cents.length < k) {
    const c = cents[cents.length - 1];
    let sum = 0;
    for (let n = 0; n < px.length; n++) {
      const i = px[n];
      const dd = (o[i] - c[0]) ** 2 + (o[i + 1] - c[1]) ** 2 + (o[i + 2] - c[2]) ** 2;
      if (dd < dmin[n]) dmin[n] = dd;
      sum += dmin[n];
    }
    let r = Math.random() * sum, pick = px[0];
    for (let n = 0; n < px.length; n++) { r -= dmin[n]; if (r <= 0) { pick = px[n]; break; } }
    cents.push([o[pick], o[pick + 1], o[pick + 2]]);
  }
  const assign = new Uint16Array(px.length);
  for (let it = 0; it < 12; it++) {
    const acc = cents.map(() => [0, 0, 0, 0]);
    for (let n = 0; n < px.length; n++) {
      const i = px[n];
      let best = 0, bd = Infinity;
      for (let c = 0; c < k; c++) {
        const C = cents[c];
        const dd = (o[i] - C[0]) ** 2 + (o[i + 1] - C[1]) ** 2 + (o[i + 2] - C[2]) ** 2;
        if (dd < bd) { bd = dd; best = c; }
      }
      assign[n] = best;
      const A = acc[best]; A[0] += o[i]; A[1] += o[i + 1]; A[2] += o[i + 2]; A[3]++;
    }
    acc.forEach((A, c) => { if (A[3]) cents[c] = [A[0] / A[3], A[1] / A[3], A[2] / A[3]]; });
  }
  for (let n = 0; n < px.length; n++) {
    const i = px[n], C = cents[assign[n]];
    o[i] = Math.round(C[0]); o[i + 1] = Math.round(C[1]); o[i + 2] = Math.round(C[2]);
  }
}

$('#btnArka').onclick = () => {
  if (!needWS()) return;
  pushHistory();
  const r = removeBackground(WS.canvas, +$('#tol').value);
  drawWorkshop();
  toast(r > 0.95 ? 'Neredeyse her şey silindi — toleransı düşür' : r < 0.02 ? 'Pek bir şey silinmedi — toleransı artır' : 'Arka plan silindi');
};
/* ---- Yapay zekâ ile düzenleme (metinle / boyayarak) ---- */
async function aiEdit(c, prompt, strength, maskCanvas) {
  const { url, key } = modalCfg();
  if (!url) throw new Error('Modal motor adresi yok');
  const body = { image: c.toDataURL('image/png').split(',')[1], prompt, strength, style: $('#stil').value === 'pixel' ? 'pixel' : 'other', lora: loraFor($('#stil').value), seed: Math.floor(Math.random() * 1e9), auto: true };
  if (maskCanvas) body.mask = maskCanvas.toDataURL('image/png').split(',')[1];
  if (REF.b64) { body.reference = REF.b64; body.ref_scale = Math.min(0.6, REF.scale); }
  const r = await fetch(url.replace(/\/+$/, '') + '/edit', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sprite-Key': key }, body: JSON.stringify(body),
  });
  if (r.status === 401) throw new Error('Motor anahtarı yanlış');
  if (!r.ok) throw new Error('Modal hatası ' + r.status);
  const d = await r.json();
  return blobToCanvas(new Blob([Uint8Array.from(atob(d.images[0]), ch => ch.charCodeAt(0))], { type: 'image/png' }));
}
async function duzenleCalistir(maskeli) {
  if (!needWS()) return;
  const metin = $('#duzenMetin').value.trim();
  if (!metin) return toast('Ne değişsin, yaz');
  const mk = $('#cvMaske');
  if (maskeli && !maskeDolu()) return toast('Önce değişecek yeri boya');
  const btn = maskeli ? $('#btnBoyaCiz') : $('#btnDuzenle');
  const t = btn.textContent; btn.disabled = true; btn.textContent = 'Çiziliyor...';
  try {
    const { en } = await interpret(metin, 'serbest', '');
    const stil = $('#stil').value;
    const prompt = [stil === 'pixel' ? 'pixel art' : '', en, WS.en, STIL[stil]].filter(Boolean).join(', ');
    const out = await aiEdit(WS.canvas, prompt, maskeli ? 0.95 : +$('#duzenGuc').value, maskeli ? mk : null);
    pushHistory(); WS.canvas = out; drawWorkshop();
    if (maskeli) maskeTemizle();
    toast('Düzenlendi — beğenmezsen "Geri al"');
  } catch (e) { toast('Olmadı: ' + e.message, 4000); }
  finally { btn.disabled = false; btn.textContent = t; }
}
$('#btnDuzenle').onclick = () => duzenleCalistir(false);
$('#btnBoyaCiz').onclick = () => duzenleCalistir(true);
$('#duzenGuc').oninput = e => $('#oGuc').textContent = e.target.value;
$('#firca').oninput = e => $('#oFirca').textContent = e.target.value;
$('#btnBoyaMod').onclick = () => {
  if (!needWS()) return;
  const on = $('#boyaAraclar').hidden;
  $('#boyaAraclar').hidden = !on;
  document.querySelector('.boyakap').classList.toggle('on', on);
  $('#btnBoyaMod').textContent = on ? '✓ Boyama açık' : '🖌 Boyayarak düzenle';
};
function maskeTemizle() { const mk = $('#cvMaske'); mk.getContext('2d').clearRect(0, 0, mk.width, mk.height); }
function maskeDolu() {
  const mk = $('#cvMaske'), d = mk.getContext('2d').getImageData(0, 0, mk.width, mk.height).data;
  for (let i = 3; i < d.length; i += 16) if (d[i]) return true;
  return false;
}
$('#btnBoyaTemizle').onclick = maskeTemizle;
(() => {
  const mk = $('#cvMaske'); let ciz = false, son = null;
  const nokta = e => { const r = mk.getBoundingClientRect(); return [(e.clientX - r.left) * mk.width / r.width, (e.clientY - r.top) * mk.height / r.height]; };
  const firca = () => +$('#firca').value * mk.width / Math.max(1, mk.getBoundingClientRect().width);
  const cizgi = (a, b) => { const x = mk.getContext('2d'); x.strokeStyle = x.fillStyle = '#ff3b6b'; x.lineWidth = firca(); x.lineCap = 'round'; x.beginPath(); x.moveTo(...a); x.lineTo(...b); x.stroke(); };
  mk.addEventListener('pointerdown', e => { ciz = true; son = nokta(e); cizgi(son, son); mk.setPointerCapture(e.pointerId); e.preventDefault(); });
  mk.addEventListener('pointermove', e => { if (!ciz) return; const p = nokta(e); cizgi(son, p); son = p; e.preventDefault(); });
  ['pointerup', 'pointercancel'].forEach(t => mk.addEventListener(t, () => { ciz = false; }));
})();

/* Parçalara ayır: arka planı silinmiş görselde birbirinden ayrı duran figürleri ayrı sprite yap */
function splitComponents(c, minFrac = 0.01) {
  const w = c.width, h = c.height;
  const d = c.getContext('2d').getImageData(0, 0, w, h).data;
  const lab = new Int32Array(w * h).fill(-1);
  const boxes = [];
  const stack = [];
  for (let p0 = 0; p0 < w * h; p0++) {
    if (lab[p0] !== -1 || d[p0 * 4 + 3] < 40) continue;
    const id = boxes.length;
    const b = { x0: w, y0: h, x1: 0, y1: 0, n: 0 };
    lab[p0] = id; stack.push(p0);
    while (stack.length) {
      const p = stack.pop();
      const x = p % w, y = (p / w) | 0;
      b.n++; if (x < b.x0) b.x0 = x; if (x > b.x1) b.x1 = x; if (y < b.y0) b.y0 = y; if (y > b.y1) b.y1 = y;
      // 8 komşu + 2 px boşluk toleransı (ince kopuklukları birleştir)
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        const q = ny * w + nx;
        if (lab[q] === -1 && d[q * 4 + 3] >= 40) { lab[q] = id; stack.push(q); }
      }
    }
    boxes.push(b);
  }
  const total = boxes.reduce((s, b) => s + b.n, 0);
  const big = boxes.filter(b => b.n >= total * minFrac);
  // satır satır, soldan sağa sırala
  const avgH = big.reduce((s, b) => s + (b.y1 - b.y0), 0) / Math.max(1, big.length);
  big.sort((a, b) => Math.abs(a.y0 - b.y0) > avgH / 2 ? a.y0 - b.y0 : a.x0 - b.x0);
  return big.map(b => {
    const out = newCanvas(b.x1 - b.x0 + 3, b.y1 - b.y0 + 3);
    const id = boxes.indexOf(b);
    const src = c.getContext('2d').getImageData(b.x0, b.y0, out.width - 2, out.height - 2);
    for (let y = 0; y < src.height; y++) for (let x = 0; x < src.width; x++) {
      const gp = (b.y0 + y) * w + b.x0 + x;
      if (lab[gp] !== id) src.data[(y * src.width + x) * 4 + 3] = 0;
    }
    out.getContext('2d').putImageData(src, 1, 1);
    return out;
  });
}
$('#btnBol').onclick = async () => {
  if (!needWS()) return;
  const parts = splitComponents(WS.canvas);
  if (parts.length < 2) return toast('Ayrı figür bulunamadı. Önce "Arka planı sil" yap.', 3500);
  if (!confirm(parts.length + ' ayrı figür bulundu. Hepsi galeriye kaydedilsin mi?')) return;
  for (let i = 0; i < parts.length; i++) await saveToGallery(parts[i], `${WS.name} ${i + 1}`, 'parça');
  toast(parts.length + ' figür galeriye kaydedildi');
  pushHistory(); WS.canvas = parts[0]; drawWorkshop();
};
async function aiRemoveBg(c) {
  const { url, key } = modalCfg();
  if (!url) throw new Error('Modal motor adresi yok');
  const b64 = (await canvasToDataURL(c)).split(',')[1];
  const r = await fetch(url.replace(/\/+$/, '') + '/rembg', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sprite-Key': key },
    body: JSON.stringify({ image: b64 }),
  });
  if (r.status === 401) throw new Error('Motor anahtarı yanlış');
  if (!r.ok) throw new Error('Modal hatası ' + r.status);
  const d = await r.json();
  const bin = Uint8Array.from(atob(d.image), ch => ch.charCodeAt(0));
  return blobToCanvas(new Blob([bin], { type: 'image/png' }));
}
function canvasToDataURL(c) { return Promise.resolve(c.toDataURL('image/png')); }
$('#btnArkaAI').onclick = async () => {
  if (!needWS()) return;
  const b = $('#btnArkaAI'); b.disabled = true; const t = b.textContent; b.textContent = 'Siliniyor...';
  try {
    const out = await aiRemoveBg(WS.canvas);
    pushHistory(); WS.canvas = out; drawWorkshop(); toast('Arka plan silindi (yapay zekâ)');
  } catch (e) { toast('Olmadı: ' + e.message + ' — normal silmeyi dene', 4000); }
  finally { b.disabled = false; b.textContent = t; }
};
$('#btnKirp').onclick = () => { if (!needWS()) return; pushHistory(); WS.canvas = trimCanvas(WS.canvas); drawWorkshop(); };
$('#btnPixel').onclick = () => {
  if (!needWS()) return;
  pushHistory();
  WS.canvas = pixelate(trimCanvas(WS.canvas, 0), +$('#pxBoyut').value, +$('#pxRenk').value, $('#kontur').checked, $('#konturRenk').value);
  drawWorkshop();
};
$('#btnGeri').onclick = () => { if (WS.history.length) { WS.canvas = WS.history.pop(); drawWorkshop(); } else toast('Geri alınacak adım yok'); };
$('#btnKaydet').onclick = async () => { if (!needWS()) return; await saveToGallery(WS.canvas, WS.name); toast('Galeriye kaydedildi'); };
$('#btnIndir').onclick = async () => { if (!needWS()) return; downloadBlob(await canvasToBlob(WS.canvas), slug(WS.name) + '.png'); };
$('#btnAnimeGonder').onclick = () => { if (!needWS()) return; AN.src = cloneCanvas(WS.canvas); AN.name = WS.name; openTab('anim'); buildAnimation(); };

/* ---------------- Kodla animasyon ---------------- */
const AN = { src: null, name: 'sprite', frames: [], timer: null };
$('#btnAnimSec').onclick = async () => {
  const [it] = await pickFromGallery('Animasyon için sprite seç', false);
  if (it) { AN.src = await blobToCanvas(it.blob); AN.name = it.name; buildAnimation(); }
};
$('#btnAnimUret').onclick = () => { if (!AN.src) return toast('Önce sprite seç'); buildAnimation(); };

function animTransform(kind, t, i, n, dir, w, h) {
  // dönüş: {dx, dy, rot, sx, sy, alpha, flash}
  const T = { dx: 0, dy: 0, rot: 0, sx: 1, sy: 1, alpha: 1, flash: 0 };
  const TAU = Math.PI * 2;
  switch (kind) {
    case 'idle': {
      const k = 0.5 - 0.5 * Math.cos(TAU * t);
      T.sy = 1 - 0.05 * k; T.sx = 1 + 0.025 * k; break;
    }
    case 'walk': {
      T.dy = -Math.abs(Math.sin(TAU * t)) * h * 0.06;
      T.rot = Math.sin(TAU * t) * 0.07 * dir;
      break;
    }
    case 'run': {
      const b = Math.abs(Math.sin(TAU * t));
      T.dy = -b * h * 0.11;
      T.rot = (0.12 + Math.sin(TAU * t) * 0.05) * dir;
      T.sy = 1 - (1 - b) * 0.06; T.sx = 1 + (1 - b) * 0.04;
      break;
    }
    case 'attack': {
      if (t < 0.4) { const e = t / 0.4; T.dx = -w * 0.08 * e * dir; T.rot = -0.12 * e * dir; }
      else if (t < 0.6) { const e = (t - 0.4) / 0.2; T.dx = (-0.08 + 0.3 * e) * w * dir; T.rot = (-0.12 + 0.32 * e) * dir; T.sx = 1 + 0.08 * e; }
      else { const e = (t - 0.6) / 0.4; T.dx = 0.22 * (1 - e) * w * dir; T.rot = 0.2 * (1 - e) * dir; T.sx = 1 + 0.08 * (1 - e); }
      break;
    }
    case 'hit': {
      T.dx = (i % 2 ? 1 : -1) * w * 0.06 * (1 - t) - w * 0.05 * dir * (1 - t);
      T.rot = -0.1 * dir * (1 - t);
      T.flash = i < Math.max(1, Math.round(n / 3)) ? 0.85 : 0;
      break;
    }
    case 'death': {
      const e = Math.min(1, t / 0.7);
      const ease = 1 - (1 - e) * (1 - e);
      T.rot = ease * Math.PI / 2 * -dir;
      T.dy = ease * h * 0.05;
      T.alpha = t > 0.7 ? 1 - (t - 0.7) / 0.3 * 0.8 : 1;
      T.flash = i === 0 ? 0.7 : 0;
      break;
    }
    case 'float': {
      T.dy = Math.sin(TAU * t) * h * 0.07;
      T.rot = Math.sin(TAU * t + 1) * 0.04;
      break;
    }
    case 'spin': {
      let c = Math.cos(TAU * t);
      if (Math.abs(c) < 0.12) c = 0.12 * Math.sign(c || 1);
      T.sx = c; break;
    }
  }
  return T;
}

function buildAnimation() {
  if (!AN.src) return;
  const kind = $('#animTur').value, n = +$('#animKare').value, dir = +$('#animYon').value;
  const w = AN.src.width, h = AN.src.height;
  const pad = Math.ceil(Math.max(w, h) * (kind === 'death' ? 0.6 : kind === 'attack' || kind === 'run' ? 0.35 : 0.2));
  const FW = w + pad * 2, FH = h + pad * 2;
  const footX = FW / 2, footY = pad + h;
  // beyaz flaş için hazır kopya
  const white = newCanvas(w, h);
  const wctx = white.getContext('2d');
  wctx.drawImage(AN.src, 0, 0);
  wctx.globalCompositeOperation = 'source-in';
  wctx.fillStyle = '#fff'; wctx.fillRect(0, 0, w, h);

  AN.frames = [];
  for (let i = 0; i < n; i++) {
    const t = i / n;
    const T = animTransform(kind, t, i, n, dir, w, h);
    const f = newCanvas(FW, FH);
    const c = f.getContext('2d');
    c.imageSmoothingEnabled = false;
    // death'te dönüş merkezi ayak yerine gövde ortası
    const pivotY = kind === 'death' ? footY - h * 0.3 : footY;
    c.translate(Math.round(footX + T.dx), Math.round(pivotY + T.dy));
    c.rotate(T.rot);
    c.scale(T.sx, T.sy);
    c.globalAlpha = T.alpha;
    const ox = -w / 2, oy = -h + (footY - pivotY);
    c.drawImage(AN.src, Math.round(ox), Math.round(oy));
    if (T.flash) { c.globalAlpha = T.flash * T.alpha; c.drawImage(white, Math.round(ox), Math.round(oy)); }
    AN.frames.push(cleanAlpha(f));
  }
  renderAnimStrip();
  playAnim();
}
/* Döndürme sonrası yarı saydam pikselleri temizle (pixel art net kalsın) */
function cleanAlpha(c) {
  const ctx = c.getContext('2d');
  const id = ctx.getImageData(0, 0, c.width, c.height), d = id.data;
  for (let i = 3; i < d.length; i += 4) d[i] = d[i] >= 100 ? (d[i] > 230 ? 255 : d[i]) : 0;
  ctx.putImageData(id, 0, 0);
  return c;
}
function renderAnimStrip() {
  const s = $('#animKareler'); s.innerHTML = '';
  AN.frames.forEach(f => { const c = cloneCanvas(f); s.appendChild(c); });
}
function playAnim() {
  clearInterval(AN.timer);
  if (!AN.frames.length) return;
  const v = $('#cvAnim');
  v.width = AN.frames[0].width; v.height = AN.frames[0].height;
  showScaled(v, 320);
  const ctx = v.getContext('2d');
  let k = 0;
  const fps = Math.max(1, Math.min(30, +$('#animFps').value || 8));
  AN.timer = setInterval(() => {
    ctx.clearRect(0, 0, v.width, v.height);
    ctx.drawImage(AN.frames[k % AN.frames.length], 0, 0);
    k++;
  }, 1000 / fps);
}
['#animTur', '#animKare', '#animYon'].forEach(s => $(s).onchange = () => AN.src && buildAnimation());
$('#animFps').onchange = playAnim;
$('#btnAnimSheet').onclick = () => {
  if (!AN.frames.length) return toast('Önce animasyon oluştur');
  SH.frames.push(...AN.frames.map(cloneCanvas));
  $('#sheetAd').value = $('#animTur').value;
  $('#sheetFps').value = $('#animFps').value;
  $('#sheetSutun').value = AN.frames.length;
  SH.name = AN.name;
  renderSheetStrip();
  openTab('sheet');
  buildSheet();
};
$('#btnAnimGaleri').onclick = async () => {
  if (!AN.frames.length) return toast('Önce animasyon oluştur');
  const kind = $('#animTur').value;
  for (let i = 0; i < AN.frames.length; i++) await saveToGallery(AN.frames[i], `${AN.name} ${kind} ${i + 1}`, 'kare');
  toast(AN.frames.length + ' kare kaydedildi');
};

/* ---------------- Sprite sheet ---------------- */
const SH = { frames: [], sheet: null, meta: null, name: 'sprite', timer: null };
$('#btnSheetEkle').onclick = async () => {
  const items = await pickFromGallery('Kareleri sırayla seç', true);
  for (const it of items) SH.frames.push(await blobToCanvas(it.blob));
  if (items.length) SH.name = items[0].name.replace(/\s*\d+$/, '');
  renderSheetStrip();
};
$('#btnSheetTemizle').onclick = () => { SH.frames = []; renderSheetStrip(); };
function renderSheetStrip() {
  const s = $('#sheetKareler'); s.innerHTML = '';
  SH.frames.forEach((f, i) => {
    const c = cloneCanvas(f);
    c.title = 'Kaldırmak için dokun';
    c.onclick = () => { SH.frames.splice(i, 1); renderSheetStrip(); toast('Kare kaldırıldı'); };
    s.appendChild(c);
  });
  if (!SH.frames.length) s.innerHTML = '<p class="hint">Kare yok.</p>';
}
function buildSheet() {
  if (!SH.frames.length) return toast('Önce kare ekle');
  const cols = Math.max(1, +$('#sheetSutun').value || 1);
  const sp = Math.max(0, +$('#sheetBosluk').value || 0);
  const cw = Math.max(...SH.frames.map(f => f.width));
  const ch = Math.max(...SH.frames.map(f => f.height));
  const rows = Math.ceil(SH.frames.length / cols);
  const realCols = Math.min(cols, SH.frames.length);
  const sheet = newCanvas(realCols * cw + (realCols - 1) * sp, rows * ch + (rows - 1) * sp);
  const ctx = sheet.getContext('2d');
  const frames = [];
  SH.frames.forEach((f, i) => {
    const x = (i % cols) * (cw + sp), y = Math.floor(i / cols) * (ch + sp);
    // alt-orta hizalama (ayaklar aynı çizgide)
    ctx.drawImage(f, x + Math.floor((cw - f.width) / 2), y + (ch - f.height));
    frames.push({ x, y, w: cw, h: ch });
  });
  const anim = slug($('#sheetAd').value || 'anim').replace(/-/g, '_');
  const fps = Math.max(1, +$('#sheetFps').value || 8);
  SH.sheet = sheet;
  SH.meta = {
    image: `${slug(SH.name)}_${anim}.png`, animation: anim, fps, loop: !/death|olum/.test(anim),
    frameWidth: cw, frameHeight: ch, columns: realCols, rows, spacing: sp, frameCount: frames.length, frames,
  };
  const v = $('#cvSheet');
  v.width = sheet.width; v.height = sheet.height;
  v.getContext('2d').drawImage(sheet, 0, 0);
  showScaled(v, 640);
  // önizleme
  clearInterval(SH.timer);
  const p = $('#cvSheetOnizle'); p.width = cw; p.height = ch; showScaled(p, 200);
  const pc = p.getContext('2d'); let k = 0;
  SH.timer = setInterval(() => {
    const fr = frames[k++ % frames.length];
    pc.clearRect(0, 0, cw, ch);
    pc.drawImage(sheet, fr.x, fr.y, cw, ch, 0, 0, cw, ch);
  }, 1000 / fps);
}
$('#btnSheetYap').onclick = buildSheet;
$('#btnSheetPng').onclick = async () => { if (!SH.sheet) return toast('Önce sheet oluştur'); downloadBlob(await canvasToBlob(SH.sheet), SH.meta.image); };
$('#btnSheetJson').onclick = () => {
  if (!SH.meta) return toast('Önce sheet oluştur');
  downloadBlob(new Blob([JSON.stringify(SH.meta, null, 2)], { type: 'application/json' }), SH.meta.image.replace('.png', '.json'));
};
function godotTres(meta, resPath) {
  const n = meta.frames.length;
  let s = `[gd_resource type="SpriteFrames" load_steps=${n + 2} format=3]\n\n`;
  s += `[ext_resource type="Texture2D" path="${resPath}" id="1_tex"]\n\n`;
  meta.frames.forEach((f, i) => {
    s += `[sub_resource type="AtlasTexture" id="AtlasTexture_${i}"]\natlas = ExtResource("1_tex")\nregion = Rect2(${f.x}, ${f.y}, ${f.w}, ${f.h})\n\n`;
  });
  s += `[resource]\nanimations = [{\n"frames": [`;
  s += meta.frames.map((_, i) => `{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_${i}")\n}`).join(', ');
  s += `],\n"loop": ${meta.loop},\n"name": &"${meta.animation}",\n"speed": ${meta.fps.toFixed(1)}\n}]\n`;
  return s;
}
$('#btnSheetTres').onclick = () => {
  if (!SH.meta) return toast('Önce sheet oluştur');
  const path = 'res://assets/sprites/' + SH.meta.image;
  downloadBlob(new Blob([godotTres(SH.meta, path)], { type: 'text/plain' }), SH.meta.image.replace('.png', '.tres'));
  toast('PNG\'yi Godot projesinde ' + path + ' yoluna koy', 4000);
};

/* ---------------- ZIP (sıkıştırmasız) — galeriyi tek dosyada indir ---------------- */
const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(u8) { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = CRC_T[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function makeZip(files) {
  const enc = new TextEncoder();
  const chunks = [], central = [];
  let off = 0;
  for (const f of files) {
    const name = enc.encode(f.name), data = f.data, crc = crc32(data);
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true);
    lh.setUint32(14, crc, true); lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true);
    lh.setUint16(26, name.length, true);
    chunks.push(new Uint8Array(lh.buffer), name, data);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true);
    ch.setUint32(16, crc, true); ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true);
    ch.setUint16(28, name.length, true); ch.setUint32(42, off, true);
    central.push(new Uint8Array(ch.buffer), name);
    off += 30 + name.length + data.length;
  }
  const csize = central.reduce((s, c) => s + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
  end.setUint32(12, csize, true); end.setUint32(16, off, true);
  return new Blob([...chunks, ...central, new Uint8Array(end.buffer)], { type: 'application/zip' });
}
$('#btnGaleriZip').onclick = async () => {
  const items = await DB.all();
  if (!items.length) return toast('Galeri boş');
  const used = new Set();
  const files = [];
  for (const it of items) {
    let nm = slug(it.name), k = 1;
    while (used.has(nm)) nm = slug(it.name) + '-' + (++k);
    used.add(nm);
    files.push({ name: nm + '.png', data: new Uint8Array(await it.blob.arrayBuffer()) });
  }
  downloadBlob(makeZip(files), 'sprite-atolye-galeri.zip');
};

/* Başlangıç */
renderSheetStrip();
