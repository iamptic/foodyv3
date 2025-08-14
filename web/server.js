// Lightweight prod server for Railway: serves dist and proxies /api to BACKEND_URL
import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
const BACKEND = process.env.BACKEND_URL || 'https://backend-production-a417.up.railway.app'

app.use('/api', createProxyMiddleware({
  target: BACKEND,
  changeOrigin: true,
  xfwd: true
  // If your backend does NOT include '/api' prefix internally, enable rewrite:
  // , pathRewrite: { '^/api': '' }
}))

const distDir = path.join(process.cwd(), 'dist')
app.use(express.static(distDir))
app.get('*', (_, res) => res.sendFile(path.join(distDir, 'index.html')))

const PORT = process.env.PORT || 8080
app.listen(PORT, '0.0.0.0', () => {
  console.log(`[web] up on :${PORT}, proxy ->`, BACKEND)
})
