/* IRTC member features on Supabase.
   The site was written against a small document-database interface (claude.use('db'|'user'|'room'));
   this file provides that same interface backed by Supabase, so the site code stays unchanged. */
(function(){
  const SUPA_URL = 'https://lnimjecbyslmcntliyvg.supabase.co';
  const SUPA_KEY = 'sb_publishable_j9gbCmYlDqIZfi0ZFpaqxg_CbmgKezI';
  const ADMIN_EMAIL = 'douggarceau@gmail.com';
  if(!window.supabase || !window.supabase.createClient){ console.warn('[irtc] Supabase library failed to load'); return; }
  const sb = window.supabase.createClient(SUPA_URL, SUPA_KEY, { auth:{ persistSession:true, autoRefreshToken:true, detectSessionInUrl:true } });

  /* ---------- auth helpers used by the sign-in screens ---------- */
  const here = () => location.origin + location.pathname;
  const sessionReady = sb.auth.getSession().then(r => (r && r.data && r.data.session) || null).catch(() => null);
  window.irtcAuth = {
    client: sb,
    session: () => sessionReady,
    signIn: async (email, password) => { const { error } = await sb.auth.signInWithPassword({ email, password }); if(error) throw error; },
    sendLink: async (email) => { const { error } = await sb.auth.signInWithOtp({ email, options:{ shouldCreateUser:false, emailRedirectTo:here() } }); if(error) throw error; },
    sendReset: async (email) => { const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo:here() }); if(error) throw error; },
    setPassword: async (password) => { const { error } = await sb.auth.updateUser({ password }); if(error) throw error; },
    signOut: async () => { try{ await sb.auth.signOut(); }catch(e){} location.reload(); },
    recovering: false,
    status: 'signedout',          // signedout | approved | pending | denied | none
    request: null,                // this person's own join request, if any
    // New person: create an account and file a request to join.
    signUp: async (email, password, info) => {
      const { data, error } = await sb.auth.signUp({ email, password, options:{ data:{ name:info.name }, emailRedirectTo:here() } });
      if(error) throw error;
      if(!data.session) return 'confirm';   // email confirmation is switched on in Supabase
      const { error: e2 } = await sb.from('join_requests').insert({ uid:data.user.id, email, name:info.name, org:info.org, note:info.note });
      if(e2 && !/duplicate/i.test(e2.message || '')) throw e2;
      return 'requested';
    },
    // Signed in but no request on file yet.
    requestAccess: async (info) => {
      const s = await sessionReady; if(!s) throw new Error('Not signed in');
      const { error } = await sb.from('join_requests').insert({ uid:s.user.id, email:s.user.email, name:info.name, org:info.org, note:info.note });
      if(error) throw error;
    },
    // Webmaster only (the database refuses everyone else).
    listRequests: async () => {
      const { data, error } = await sb.from('join_requests').select('*').order('created_at', { ascending:false }).limit(500);
      if(error) throw error; return data || [];
    },
    // Photos and videos for posts live in the private 'media' storage bucket.
    upload: async (file, name) => {
      const s = await sessionReady; if(!s) throw new Error('Not signed in');
      const safe = String(name || file.name || 'file').replace(/[^\w.-]+/g, '_').slice(-60);
      const path = s.user.id + '/' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6) + '-' + safe;
      const { error } = await sb.storage.from('media').upload(path, file, { contentType:file.type || 'application/octet-stream', upsert:false });
      if(error) throw error; return path;
    },
    mediaUrl: (() => { const cache = {}; return async (path) => {
      const hit = cache[path]; if(hit && hit.exp > Date.now()) return hit.url;
      const { data, error } = await sb.storage.from('media').createSignedUrl(path, 3600 * 6);
      if(error) throw error; cache[path] = { url:data.signedUrl, exp:Date.now() + 3600 * 5 * 1000 }; return data.signedUrl;
    }; })(),
    removeMedia: async (paths) => { if(paths && paths.length) await sb.storage.from('media').remove(paths); },
    decide: async (uid, status) => {
      const { error } = await sb.from('join_requests').update({ status, decided_at:new Date().toISOString() }).eq('uid', uid);
      if(error) throw error;
    }
  };
  if(/type=recovery/.test(location.hash)) window.irtcAuth.recovering = true;
  sb.auth.onAuthStateChange((ev) => {
    if(ev === 'PASSWORD_RECOVERY'){ window.irtcAuth.recovering = true; window.dispatchEvent(new Event('irtc-recovery')); }
  });

  /* ---------- document paths ---------- */
  // 'members/abc' -> {coll:'members', id:'abc'};  'data/users/abc/keys' -> {coll:'private', id:'abc/keys'}
  function split(path){
    const p = String(path).split('/');
    if(p[0] === 'data' && p[1] === 'users') return { coll:'private', id:p.slice(2).join('/') };
    return { coll:p[0], id:p.slice(1).join('/') };
  }
  const err = (e) => { const x = new Error((e && e.message) || 'Database error'); x.code = (e && /permission|policy|row-level/i.test(e.message || '')) ? 'invalid_argument' : 'unavailable'; return x; };
  const docSnap = (id, row) => ({ id, exists: !!row, data: () => (row ? row.data : undefined) });

  /* ---------- live listeners ---------- */
  const listeners = new Map();          // coll -> Set of refresh functions
  const membersCache = {};              // id -> member data, for names and photos
  function on(coll, fn){ if(!listeners.has(coll)) listeners.set(coll, new Set()); listeners.get(coll).add(fn); return () => listeners.get(coll).delete(fn); }
  const pending = new Map();
  function notify(coll){
    if(pending.has(coll)) return;
    pending.set(coll, setTimeout(() => { pending.delete(coll); (listeners.get(coll) || []).forEach(fn => { try{ fn(); }catch(e){} }); }, 120));
  }
  let channel = null;
  function startRealtime(){
    if(channel) return;
    channel = sb.channel('irtc-docs')
      .on('postgres_changes', { event:'*', schema:'public', table:'docs' }, (p) => { const c = (p.new && p.new.coll) || (p.old && p.old.coll); if(c) notify(c); else listeners.forEach((_, k) => notify(k)); })
      .subscribe();
    // Safety net: refresh everything every 45 seconds and whenever the tab comes back into view.
    setInterval(() => listeners.forEach((_, k) => notify(k)), 45000);
    document.addEventListener('visibilitychange', () => { if(!document.hidden) listeners.forEach((_, k) => notify(k)); });
  }

  async function fetchColl(coll){
    const { data, error } = await sb.from('docs').select('id,data').eq('coll', coll).limit(5000);
    if(error) throw err(error);
    if(coll === 'members'){ for(const k of Object.keys(membersCache)) delete membersCache[k]; for(const r of data) membersCache[r.id] = r.data || {}; }
    return data;
  }
  async function fetchDoc(coll, id){
    const { data, error } = await sb.from('docs').select('id,data').eq('coll', coll).eq('id', id).maybeSingle();
    if(error) throw err(error);
    return data;
  }

  function makeDb(){
    startRealtime();
    return {
      collection(path){
        const coll = split(path + '/x').coll;
        return {
          onSnapshot(cb, onErr){
            const run = async () => { try{ const rows = await fetchColl(coll); cb({ docs: rows.map(r => docSnap(r.id, r)), size: rows.length, empty: !rows.length }); }catch(e){ if(onErr) onErr(e); } };
            const off = on(coll, run); run(); return off;
          },
          async get(){ const rows = await fetchColl(coll); return { docs: rows.map(r => docSnap(r.id, r)), size: rows.length, empty: !rows.length }; }
        };
      },
      doc(path){
        const { coll, id } = split(path);
        return {
          id,
          async get(){ return docSnap(id, await fetchDoc(coll, id)); },
          async set(data){
            const { error } = await sb.from('docs').upsert({ coll, id, data: data || {}, updated_at: new Date().toISOString() });
            if(error) throw err(error);
            if(coll === 'members') membersCache[id] = data || {};
            notify(coll);
          },
          async update(patch){
            const cur = await fetchDoc(coll, id);
            return this.set({ ...((cur && cur.data) || {}), ...(patch || {}) });
          },
          async delete(){
            const { error } = await sb.from('docs').delete().eq('coll', coll).eq('id', id);
            if(error) throw err(error);
            if(coll === 'members') delete membersCache[id];
            notify(coll);
          },
          onSnapshot(cb, onErr){
            const run = async () => { try{ cb(docSnap(id, await fetchDoc(coll, id))); }catch(e){ if(onErr) onErr(e); } };
            const off = on(coll, run); run(); return off;
          }
        };
      }
    };
  }

  /* ---------- people ---------- */
  const COLORS = ['#0E2A4F','#8C1D2E','#2C6E5F','#2B5794','#8A5B12','#6B4E9B','#0F766E','#B45309'];
  function avatar(id, name){
    const words = String(name || '?').trim().split(/\s+/).filter(Boolean);
    const ini = ((words[0] || '?')[0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase();
    let h = 0; for(const ch of String(id)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    const bg = COLORS[h % COLORS.length];
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><rect width="96" height="96" fill="${bg}"/><text x="48" y="50" font-family="Helvetica,Arial,sans-serif" font-size="40" font-weight="600" fill="#fff" text-anchor="middle" dominant-baseline="central">${ini.replace(/[<>&"]/g, '')}</text></svg>`;
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }
  const nameFrom = (m, email) => (m && m.name) || (email ? email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Member');

  function makeUser(session){
    const u = session.user;
    return {
      async me(){
        let m = membersCache[u.id];
        if(!m){ try{ const r = await fetchDoc('members', u.id); m = r && r.data; if(m) membersCache[u.id] = m; }catch(e){} }
        const name = nameFrom(m, u.email);
        return { id:u.id, email:u.email, name, avatarUrl:avatar(u.id, name), isOwner:(u.email || '').toLowerCase() === ADMIN_EMAIL };
      },
      async can(){ return true; },
      async profiles(ids){
        const missing = ids.filter(id => !membersCache[id]);
        if(missing.length){
          try{ const { data } = await sb.from('docs').select('id,data').eq('coll', 'members').in('id', missing.slice(0, 200)); (data || []).forEach(r => { membersCache[r.id] = r.data || {}; }); }catch(e){}
        }
        const out = {};
        for(const id of ids){ const m = membersCache[id]; const name = nameFrom(m, m && m.email); out[id] = { name, avatarUrl:avatar(id, name) }; }
        return out;
      }
    };
  }

  /* ---------- who is online ---------- */
  function makeRoom(session){
    const uid = session.user.id;
    const ch = sb.channel('irtc-online', { config:{ presence:{ key:uid } } });
    const cbs = new Set(); let joined = null, last = { show:true };
    const ready = new Promise(res => { joined = res; });
    ch.on('presence', { event:'sync' }, () => cbs.forEach(f => { try{ f(); }catch(e){} }))
      .subscribe(async (status) => { if(status === 'SUBSCRIBED'){ joined(); try{ await ch.track(last); }catch(e){} } });
    return {
      peers(){
        const st = ch.presenceState(); const out = [];
        for(const [key, metas] of Object.entries(st)){ const m = metas[metas.length - 1] || {}; out.push({ kind:'viewer', by:key, presence:{ show:m.show === true } }); }
        return out;
      },
      onPeers(f){ cbs.add(f); return () => cbs.delete(f); },
      async presence(obj){ last = obj || {}; await ready; return ch.track(last); }
    };
  }

  /* ---------- the interface the site expects ---------- */
  let cache = null;
  async function build(){
    const session = await sessionReady;
    if(!session) return { db:null, user:null, room:null };
    // Only approved members get the member features.
    const A = window.irtcAuth;
    try{
      const { data:ok, error } = await sb.rpc('irtc_is_approved');
      if(error) throw error;
      if(ok){ A.status = 'approved'; }
      else{
        const { data:row } = await sb.from('join_requests').select('*').eq('uid', session.user.id).maybeSingle();
        A.request = row || null;
        A.status = row ? row.status : 'none';
        if(A.status === 'approved') A.status = 'pending';   // safety: never unlock without the server agreeing
      }
    }catch(e){ A.status = 'approved'; }                    // approval table not set up yet: behave as before
    if(A.status !== 'approved') return { db:null, user:null, room:null };
    let room = null;
    return { db:makeDb(), user:makeUser(session), get room(){ return room || (room = makeRoom(session)); } };
  }
  window.claude = {
    irtc: true,
    async use(name){
      cache = cache || build();
      const c = await cache;
      if(name === 'db') return c.db;
      if(name === 'user') return c.user;
      if(name === 'room') return c.db ? c.room : null;
      return null; // the AI research assistant only runs inside Claude
    }
  };
})();
