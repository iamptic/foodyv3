const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');
const app = express();
const WEB_DIR = path.join(__dirname, 'web');
const FOODY_API = process.env.FOODY_API || '';

// No-cache for HTML and config.js
app.disable('etag');
app.use((req,res,next)=>{
  if (req.path.endsWith('.html') || req.path === '/' || req.path === '/config.js') {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.set('Pragma', 'no-cache');
    res.set('Expires', '0');
    res.set('Surrogate-Control', 'no-store');
  }
  next();
});
app.get('/config.js', (req,res) => {
  res.type('application/javascript').send(`window.foodyApi=${JSON.stringify(FOODY_API)};`);
});
app.use('/api', createProxyMiddleware({ target: FOODY_API, changeOrigin: true, pathRewrite: {'^/api': ''} }));
app.use('/web', express.static(WEB_DIR, { index: 'index.html', extensions: ['html'] }));
app.use(express.static(WEB_DIR, { index: 'index.html', extensions: ['html'] }));
app.get('/health', (req,res)=>res.json({ok:true}));
app.get('/', (req,res)=>res.redirect('/web/buyer/'));
const PORT = process.env.PORT || 8080;
app.listen(PORT, ()=>console.log('Foody web listening on', PORT));
