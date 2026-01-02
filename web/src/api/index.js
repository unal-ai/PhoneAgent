import axios from 'axios'
import { ElMessage } from 'element-plus'
import { requestMonitor } from './request-monitor'

// 从环境变量获取 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
  : '/api/v1'

// API configuration is loaded from environment variables

// 超时配置（针对不同类型的请求）
const TIMEOUT_CONFIG = {
  default: 30000,      // 默认 30 秒
  upload: 60000,       // 文件上传 60 秒
  stream: 120000,      // 流式请求 120 秒
  device: 30000,       // 设备操作 30 秒（支持 UI dump 重试）
  scrcpy: 60000,       // scrcpy 启动 60 秒
  planning: 45000,     // 规划生成 45 秒（AI生成计划需要时间）
  diagnostics: 10000,  // 诊断API 10 秒
}

// 创建 axios 实例
const request = axios.create({
  baseURL: API_BASE_URL,
  timeout: TIMEOUT_CONFIG.default,
  withCredentials: true  // 支持跨域携带凭证
})

// 请求ID生成器
let requestIdCounter = 0
const generateRequestId = () => `req_${Date.now()}_${++requestIdCounter}`

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 生成请求ID
    const requestId = generateRequestId()
    config.requestId = requestId

    // 动态设置超时时间
    if (config.url?.includes('/speech/stt') || config.url?.includes('/speech/tts')) {
      config.timeout = TIMEOUT_CONFIG.upload
    } else if (config.url?.includes('/scrcpy/start')) {
      config.timeout = TIMEOUT_CONFIG.scrcpy
    } else if (config.url?.includes('/devices/scanned') || config.url?.includes('/devices/')) {
      // 设备API：/devices/scanned 和 /devices/{id}（优化后应该很快）
      config.timeout = TIMEOUT_CONFIG.device
    } else if (config.url?.includes('/planning/generate')) {
      // 规划生成API需要调用LLM，时间较长
      config.timeout = TIMEOUT_CONFIG.planning
    } else if (config.url?.includes('/diagnostics/')) {
      // 诊断API应该很快
      config.timeout = TIMEOUT_CONFIG.diagnostics
    } else if (config.url?.includes('/stream')) {
      config.timeout = TIMEOUT_CONFIG.stream
    }

    // 开始监控
    requestMonitor.startRequest(requestId, config)

    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url} (timeout: ${config.timeout}ms)`)
    }

    // 可以在这里添加 token
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    // 结束监控
    const requestId = response.config.requestId
    if (requestId) {
      requestMonitor.endRequest(requestId, true)
    }

    return response.data
  },
  error => {
    // 结束监控
    const requestId = error.config?.requestId
    if (requestId) {
      requestMonitor.endRequest(requestId, false, error)
    }

    // 友好的错误提示
    let message = '请求失败'

    // 超时错误特殊处理
    if (error.code === 'ECONNABORTED' && error.message?.includes('timeout')) {
      const timeout = error.config?.timeout || TIMEOUT_CONFIG.default
      message = `请求超时（${timeout / 1000}秒），可能原因：\n1. 网络连接不稳定\n2. 服务器响应缓慢\n3. 操作耗时过长`
      ElMessage.error({
        message,
        duration: 5000,
        showClose: true
      })

      console.error(`[TIMEOUT] ${error.config?.url}`, {
        timeout: `${timeout}ms`,
        method: error.config?.method
      })
    } else if (error.response?.status === 404) {
      // 404错误不显示红色提示，让组件自己处理
      console.warn('API endpoint not found:', error.config?.url)
    } else if (error.response?.status >= 500) {
      message = '服务器内部错误，请稍后重试'
      ElMessage.error(message)
    } else if (error.code === 'ERR_NETWORK') {
      message = '网络连接失败，请检查后端服务是否启动'
      ElMessage.error(message)
    } else {
      message = error.response?.data?.detail || error.message || '请求失败'
      // 设备扫描/详情错误不弹窗（可能是设备未连接）
      if (!error.config?.url?.includes('/devices/')) {
        ElMessage.error(message)
      }
    }

    return Promise.reject(error)
  }
)

// ============================================
// 设备管理 API
// ============================================

export const deviceApi = {
  // 获取设备列表
  async list(status = null) {
    try {
      const scannedDevices = await request.get('/devices/scanned')

      // 如果scannedDevices有devices字段，返回devices数组
      if (scannedDevices && scannedDevices.devices) {
        return scannedDevices.devices
      }

      // 否则返回整个响应
      return scannedDevices
    } catch (error) {
      console.warn('V2 API failed, fallback to V1:', error)

      // V1 API已废弃，直接返回空数组
      console.warn('V2 API failed, V1 API已废弃:', error)

      // 返回空数组
      if (error.response?.status === 404) {
        console.info('No devices API available, returning empty list')
        return []
      }

      throw error
    }
  },

  // 获取设备详情
  get(deviceId) {
    return request.get(`/devices/${deviceId}`)
  }
}

// ============================================
// 任务管理 API
// ============================================

export const taskApi = {
  // 创建任务
  create(data) {
    return request.post('/tasks', data)
  },

  // 获取任务列表
  list(params = {}) {
    return request.get('/tasks', { params })
  },

  // 获取任务详情
  get(taskId) {
    return request.get(`/tasks/${taskId}`)
  },

  // 获取任务步骤详情
  getSteps(taskId) {
    return request.get(`/tasks/${taskId}/steps`)
  },

  // 取消任务
  cancel(taskId) {
    return request.post(`/tasks/${taskId}/cancel`)
  },

  // 删除任务
  delete(taskId) {
    return request.delete(`/tasks/${taskId}`)
  },

  // 批量删除任务
  deleteBatch(taskIds) {
    return request.post('/tasks/delete-batch', { task_ids: taskIds })
  },

  // 获取任务LLM上下文（用于调试）
  getContext(taskId) {
    return request.get(`/tasks/${taskId}/context`)
  },

  // 向任务注入用户评论
  inject(taskId, comment) {
    return request.post(`/tasks/${taskId}/inject`, { comment })
  }
}

// ============================================
// 统计信息 API
// ============================================

export const statsApi = {
  // 获取统计信息
  get() {
    return request.get('/stats')
  }
}

// ============================================
// 快捷指令 API
// ============================================

export const shortcutApi = {
  // 获取快捷指令列表
  list(category = null) {
    return request.get('/shortcuts', { params: { category } })
  },

  // 获取快捷指令详情
  get(shortcutId) {
    return request.get(`/shortcuts/${shortcutId}`)
  },

  // 创建快捷指令
  create(data) {
    return request.post('/shortcuts', data)
  },

  // 更新快捷指令
  update(shortcutId, data) {
    return request.put(`/shortcuts/${shortcutId}`, data)
  },

  // 删除快捷指令
  delete(shortcutId) {
    return request.delete(`/shortcuts/${shortcutId}`)
  },

  // 执行快捷指令
  execute(shortcutId, deviceId = null) {
    return request.post(`/shortcuts/${shortcutId}/execute`, { device_id: deviceId })
  },

  // 获取分类列表
  getCategories() {
    return request.get('/shortcuts/categories')
  }
}

// ============================================
// 规划模式 API (新增)
// ============================================

export const planningApi = {
  // 生成任务计划（不执行）
  generate(data) {
    return request.post('/planning/generate', data)
  },

  // 执行已生成的计划
  execute(data) {
    return request.post('/planning/execute', data)
  },

  // 直接执行（生成+执行）
  executeDirect(data) {
    return request.post('/planning/execute-direct', data)
  },

  // 列出可用的提示词卡片
  listPromptCards() {
    return request.get('/planning/prompt-cards')
  }
}

// ============================================
// 语音识别 API
// ============================================

export const speechApi = {
  // 语音转文字（智谱AI STT）
  async transcribe(audioBlob, options = {}) {
    const { apiKey, prompt } = options
    const formData = new FormData()
    formData.append('file', audioBlob, 'audio.webm')

    // 如果提供了API Key，添加到表单数据中
    if (apiKey && apiKey.trim()) {
      formData.append('api_key', apiKey.trim())
    }

    // 如果提供了提示词，添加到表单数据中
    if (prompt && prompt.trim()) {
      formData.append('prompt', prompt.trim())
    }

    try {
      // 使用正确的STT端点
      const response = await request.post('/speech/stt', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      // 返回识别结果
      return {
        text: response.text || '',
        duration: response.duration || 0
      }
    } catch (error) {
      console.error('Speech recognition error:', error)
      throw new Error('语音识别失败')
    }
  },

  // 文字转语音（智谱AI TTS）
  async textToSpeech(text, options = {}) {
    const { apiKey, voice = 'tongtong', speed = 1.0 } = options

    try {
      // 使用新的TTS API
      const response = await request.post('/speech/tts', {
        text,
        voice,
        speed,
        response_format: 'wav',
        stream: false
      }, {
        responseType: 'blob'
      })

      // 创建音频URL并播放
      const audioUrl = URL.createObjectURL(response)

      return new Promise((resolve, reject) => {
        const audio = new Audio(audioUrl)
        audio.oncanplaythrough = () => {
          audio.play()
            .then(() => {
              // 播放完成后清理URL
              audio.onended = () => URL.revokeObjectURL(audioUrl)
              resolve(audio)
            })
            .catch(reject)
        }
        audio.onerror = () => {
          URL.revokeObjectURL(audioUrl)
          reject(new Error('音频播放失败'))
        }
      })
    } catch (error) {
      console.error('TTS error:', error)
      throw new Error('文字转语音失败')
    }
  }
}

// 导出request实例
export { request }
export default request

