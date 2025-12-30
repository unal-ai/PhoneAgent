import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  const apiHost = env.VITE_API_HOST || 'localhost'
  const apiPort = env.VITE_API_PORT || '8000'
  // Note: VITE_WS_PORT (9999) 用于设备通信 WebSocket，前端 WebSocket 使用 API 端口

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      host: '0.0.0.0',  // 监听所有网络接口，允许外网访问
      port: 5173,
      // 允许所有域名访问（开源版本）
      allowedHosts: true,
      proxy: {
        '/api': {
          target: `http://${apiHost}:${apiPort}`,
          changeOrigin: true
        },
        // 前端 WebSocket 连接到 API 服务器 (port 8000) 的 /api/v1/ws 端点
        '/ws': {
          target: `ws://${apiHost}:${apiPort}`,
          ws: true,
          rewrite: (path) => `/api/v1${path}`
        }
      }
    },
    preview: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: false,
      // 允许所有域名访问（开源版本）
      allowedHosts: true,
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      },
      proxy: {
        '/api': {
          target: `http://${apiHost}:${apiPort}`,
          changeOrigin: true
        },
        // 前端 WebSocket 连接到 API 服务器 (port 8000) 的 /api/v1/ws 端点
        '/ws': {
          target: `ws://${apiHost}:${apiPort}`,
          ws: true,
          rewrite: (path) => `/api/v1${path}`
        }
      }
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: false,
      // 代码分割优化
      rollupOptions: {
        output: {
          manualChunks: {
            // 简化分包，避免循环依赖
            'vendor': ['vue', 'vue-router', 'pinia', 'axios'],
            'ui': ['element-plus', '@element-plus/icons-vue']
          },
          // 文件名优化（使用hash）
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
        }
      },
      // 提高 chunk 大小警告阈值到 1000kb（可选）
      chunkSizeWarningLimit: 1000
    }
  }
})

