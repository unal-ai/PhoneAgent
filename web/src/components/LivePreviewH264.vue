<template>
  <div class="live-preview-h264">
    <!-- 视频元素 -->
    <video 
      ref="videoRef" 
      autoplay 
      muted 
      playsinline
      @click="handleClick"
      @playing="onVideoPlaying"
      @stalled="onVideoStalled"
      @error="onVideoError"
      :class="{ 'clickable': enableControl }"
      class="video-player"
    />
    
    <!-- 状态指示器 -->
    <div class="status-overlay">
      <el-tag :type="statusType" size="small">{{ status }}</el-tag>
      <span v-if="fps > 0" class="fps-indicator">{{ fps }} FPS</span>
      <span v-if="latency > 0" class="latency-indicator">{{ latency }}ms</span>
      <el-button 
        size="small" 
        type="info" 
        circle 
        @click="showDebug = !showDebug"
        class="debug-toggle"
      >
        🔍
      </el-button>
    </div>
    
    <!-- Debug 面板 -->
    <div v-if="showDebug" class="debug-overlay">
      <div class="debug-title">🔍 视频流调试</div>
      <div class="debug-row">
        <span>NAL 单元:</span>
        <span>{{ debugStats.nalCount }}</span>
      </div>
      <div class="debug-row">
        <span>接收字节:</span>
        <span>{{ formatBytes(debugStats.totalBytes) }}</span>
      </div>
      <div class="debug-row">
        <span>视频状态:</span>
        <span :class="videoState.class">{{ videoState.text }}</span>
      </div>
      <div class="debug-row">
        <span>初始化:</span>
        <span :class="debugStats.hasReceivedInit ? 'good' : 'bad'">
          {{ debugStats.hasReceivedInit ? '✓ 已接收' : '✗ 等待中' }}
        </span>
      </div>
      <div class="debug-row">
        <span>播放时间:</span>
        <span>{{ videoRef?.currentTime?.toFixed(2) || 0 }}s</span>
      </div>
      <el-button size="small" type="warning" @click="forceReconnect">
        强制重连
      </el-button>
    </div>
    
    <!-- 加载指示 -->
    <div v-if="status === '连接中...'" class="loading-overlay">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p>正在连接视频流...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import jMuxer from 'jmuxer'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { request } from '@/api/index'

const props = defineProps({
  deviceId: {
    type: String,
    required: true
  },
  enableControl: {
    type: Boolean,
    default: false
  }
})

const videoRef = ref(null)
const status = ref('连接中...')
const statusType = ref('info')
const fps = ref(0)
const latency = ref(0)

let jmuxerInstance = null
let ws = null
let frameCount = 0
let lastCountTime = Date.now()
let reconnectTimer = null
let initSegment = null
let initScanComplete = false
let initScanAttempts = 0
const NAL_SPS = 7
const NAL_PPS = 8
const NAL_IDR = 5
const NAL_SLICE = 1  // Non-IDR slice
const MAX_INIT_SCAN_ATTEMPTS = 10
const BYTE_ZERO = 0x00
const START_CODE = 0x01
const NAL_TYPE_MASK = 0x1f

// Debug stats
const debugStats = ref({
  totalBytes: 0,
  nalCount: 0,
  hasReceivedInit: false,
  lastNalType: 0,
  hasPlayedFirstFrame: false
})

// Debug panel visibility
const showDebug = ref(false)

// Video state computed property for debug display
const videoState = computed(() => {
  if (!videoRef.value) {
    return { text: '未就绪', class: 'bad' }
  }
  if (videoRef.value.paused) {
    return { text: '暂停', class: 'warn' }
  }
  if (videoRef.value.currentTime > 0) {
    return { text: '播放中', class: 'good' }
  }
  return { text: '等待数据', class: 'warn' }
})

// Format bytes for display
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

// Force reconnect function
function forceReconnect() {
  console.log('[Debug] Force reconnecting...')
  reconnect()
}

// Video event handlers
function onVideoPlaying() {
  console.log('[Video] Started playing')
  debugStats.value.hasPlayedFirstFrame = true
  status.value = '已连接'
  statusType.value = 'success'
}

function onVideoStalled() {
  console.warn('[Video] Stalled - waiting for data')
  status.value = '缓冲中...'
}

function onVideoError(e) {
  console.error('[Video] Error:', e)
  status.value = '播放错误'
  statusType.value = 'danger'
}

function isStartCode(data, index) {
  const fourByte = index + 3 < data.length &&
    data[index] === BYTE_ZERO && data[index + 1] === BYTE_ZERO && data[index + 2] === BYTE_ZERO && data[index + 3] === START_CODE
  const threeByte = index + 2 < data.length &&
    data[index] === BYTE_ZERO && data[index + 1] === BYTE_ZERO && data[index + 2] === START_CODE
  return {
    matched: fourByte || threeByte,
    length: fourByte ? 4 : (threeByte ? 3 : 0)
  }
}

function combineInitSlices(sps, pps, idr) {
  const combined = new Uint8Array(sps.length + pps.length + idr.length)
  combined.set(sps, 0)
  combined.set(pps, sps.length)
  combined.set(idr, sps.length + pps.length)
  return combined
}

function extractInitSegment(data) {
  let sps = null
  let pps = null
  let idr = null
  let lastStart = -1
  let lastLength = 0
  
  for (let i = 0; i < data.length; i++) {
    const start = isStartCode(data, i)
    if (!start.matched) continue
    
    if (lastStart >= 0) {
      const offset = lastStart + lastLength
      if (offset < data.length) {
        const nalType = data[offset] & NAL_TYPE_MASK
        const nalSlice = data.slice(lastStart, i)
        if (nalType === NAL_SPS) sps = nalSlice
        if (nalType === NAL_PPS) pps = nalSlice
        if (nalType === NAL_IDR) idr = nalSlice
        if (sps && pps && idr) {
          return combineInitSlices(sps, pps, idr)
        }
      }
    }
    
    lastStart = i
    lastLength = start.length
    i += start.length - 1
  }
  
  if (lastStart >= 0) {
    const offset = lastStart + lastLength
    if (offset < data.length) {
      const nalType = data[offset] & NAL_TYPE_MASK
      const nalSlice = data.slice(lastStart)
      if (nalType === NAL_SPS) sps = nalSlice
      if (nalType === NAL_PPS) pps = nalSlice
      if (nalType === NAL_IDR) idr = nalSlice
    }
  }
  
  if (sps && pps && idr) {
    return combineInitSlices(sps, pps, idr)
  }
  
  return null
}

// 监听设备切换
watch(() => props.deviceId, () => {
  reconnect()
})

onMounted(() => {
  // 延迟连接，确保组件完全挂载和session已就绪
  // 增加延迟时间避免session not found错误
  setTimeout(() => {
    connect()
  }, 1000)
})

function connect() {
  status.value = '连接中...'
  statusType.value = 'info'
  
  // 检查video元素是否已就绪
  if (!videoRef.value) {
    console.error('[jMuxer] Video element not ready')
    ElMessage.error('视频元素未就绪，请刷新页面')
    return
  }
  
  try {
    // 1. 创建 jMuxer 实例
    jmuxerInstance = new jMuxer({
      node: videoRef.value,
      mode: 'video',
      flushingTime: 0,  // ✅ 零延迟刷新
      fps: 30,
      clearBuffer: true,
      debug: false,
      onError: (error) => {
        console.error('[jMuxer] Error:', error)
        
        // 智能错误恢复
        if (error.name === 'InvalidStateError' && error.error === 'buffer error') {
          console.log('[jMuxer] Buffer error, attempting reset...')
          try {
            jmuxerInstance?.reset()
            if (initSegment) {
              try {
                jmuxerInstance.feed({ video: initSegment })
                console.log('[jMuxer] Re-initialized with cached SPS/PPS/IDR')
              } catch (feedError) {
                console.error('[jMuxer] Re-init feed failed, reconnecting...', feedError)
                reconnect()
                return
              }
            } else {
              reconnect()
              return
            }
            console.log('[jMuxer] Reset successful')
          } catch (resetError) {
            console.error('[jMuxer] Reset failed:', resetError)
            ElMessage.error('视频解码器错误，正在重连...')
            reconnect()
          }
        }
      },
      onMissingVideoFrames: (frames) => {
        // jMuxer bug: 误报丢帧（H.264 slices 被当作独立帧）
        // 忽略此警告
        console.debug('[jMuxer] Missing frames (可能是误报):', frames)
      }
    })
    
    // 2. 连接 WebSocket（优先使用后端 API 地址，避免代理丢失升级请求）
    let protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    let host = location.host
    try {
      if (import.meta.env.VITE_API_BASE_URL) {
        const apiUrl = new URL(import.meta.env.VITE_API_BASE_URL)
        protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
        host = apiUrl.host
      }
    } catch (e) {
      console.warn('[WebSocket] Failed to parse VITE_API_BASE_URL, fallback to current host', e)
    }
    const wsUrl = `${protocol}//${host}/api/v1/scrcpy/stream/${encodeURIComponent(props.deviceId)}`
    
    console.log('[WebSocket] Connecting to:', wsUrl)
    ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    
    ws.onopen = () => {
      if (import.meta.env.DEV) {
        console.log('[H264Preview] WebSocket connected')
      }
      status.value = '已连接'
      statusType.value = 'success'
      startMonitors()
    }
    
    ws.onmessage = (event) => {
      // 处理错误消息
      if (typeof event.data === 'string') {
        try {
          const error = JSON.parse(event.data)
          if (error.error) {
            console.error('[Server Error]:', error)
            ElMessage.error(error.message || error.error)
            status.value = '错误'
            statusType.value = 'danger'
            return
          }
          // 忽略 ping 消息
          if (error.type === 'ping') {
            return
          }
        } catch {
          console.warn('[Unknown Message]:', event.data)
        }
        return
      }
      
      // H.264 NAL 单元数据
      if (jmuxerInstance) {
        const videoData = new Uint8Array(event.data)
        if (!initSegment && !initScanComplete) {
          if (initScanAttempts >= MAX_INIT_SCAN_ATTEMPTS) {
            initScanComplete = true
          } else {
            initScanAttempts++
            const extracted = extractInitSegment(videoData)
            if (extracted) {
              initSegment = extracted
              initScanComplete = true
            }
          }
        }
        
        // 验证 NAL unit（调试用）
        if (frameCount === 0) {
          const hasStartCode = (
            videoData[0] === 0x00 && 
            videoData[1] === 0x00 && 
            (videoData[2] === 0x00 || videoData[2] === 0x01)
          )
          console.log('[First NAL]:', {
            size: videoData.length,
            hasStartCode,
            preview: Array.from(videoData.slice(0, 8)).map(b => b.toString(16).padStart(2, '0')).join(' ')
          })
          debugStats.value.hasReceivedInit = true
        }
        
        // Update debug stats
        debugStats.value.totalBytes += videoData.length
        debugStats.value.nalCount++
        
        // Feed 数据到 jMuxer
        jmuxerInstance.feed({
          video: videoData
        })
        
        frameCount++
        
        // Check for black screen after receiving data
        // If we've received 30+ frames but video is not playing, warn user
        if (frameCount === 30 && videoRef.value) {
          setTimeout(() => {
            if (videoRef.value && videoRef.value.currentTime === 0) {
              console.warn('[jMuxer] Video not playing after 30 frames, possible decode issue')
              status.value = '解码中...'
              // Consider auto-reconnect after more frames
            }
          }, 1000)
        }
      }
    }
    
    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
      status.value = '连接错误'
      statusType.value = 'danger'
      ElMessage.error('WebSocket 连接失败')
    }
    
    ws.onclose = (event) => {
      console.log('[WebSocket] Closed:', event.code, event.reason)
      status.value = '已断开'
      statusType.value = 'warning'
      
      // 3秒后自动重连
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
      reconnectTimer = setTimeout(() => {
        console.log('[WebSocket] Reconnecting...')
        reconnect()
      }, 3000)
    }
    
  } catch (error) {
    console.error('[Init Error]:', error)
    ElMessage.error('初始化失败: ' + error.message)
    status.value = '初始化失败'
    statusType.value = 'danger'
  }
}

function reconnect() {
  // 清理旧连接
  if (ws) {
    try {
      // Prevent triggering onclose which schedules another reconnect
      ws.onclose = null
      ws.close()
    } catch {}
    ws = null
  }
  
  if (jmuxerInstance) {
    try {
      jmuxerInstance.destroy()
    } catch {}
    jmuxerInstance = null
  }
  
  // 重置状态
  frameCount = 0
  fps.value = 0
  initSegment = null
  initScanComplete = false
  initScanAttempts = 0
  debugStats.value = {
    totalBytes: 0,
    nalCount: 0,
    hasReceivedInit: false,
    lastNalType: 0,
    hasPlayedFirstFrame: false
  }
  
  // 300ms 后重新连接（让资源释放）
  setTimeout(connect, 300)
}

function startMonitors() {
  // FPS 计数器
  setInterval(() => {
    const now = Date.now()
    const elapsed = now - lastCountTime
    fps.value = Math.round((frameCount / elapsed) * 1000)
    
    frameCount = 0
    lastCountTime = now
  }, 2000)
  
  // 延迟监控（简易版）
  setInterval(() => {
    if (videoRef.value && videoRef.value.buffered.length > 0) {
      const buffered = videoRef.value.buffered.end(0) - videoRef.value.currentTime
      latency.value = Math.round(buffered * 1000)
    }
  }, 1000)
}

async function handleClick(event) {
  if (!props.enableControl) return
  
  const rect = videoRef.value.getBoundingClientRect()
  const x = Math.round((event.clientX - rect.left) / rect.width * 100)
  const y = Math.round((event.clientY - rect.top) / rect.height * 100)
  
  // 发送触摸事件到后端
  try {
    await request.post(`/scrcpy/control/${props.deviceId}/touch`, {
      x: x,
      y: y,
      action: 'tap'
    })
    console.log('[Click Success]:', x, y)
  } catch (error) {
    console.error('[Click Error]:', error)
    ElMessage.error('点击失败: ' + (error.message || '未知错误'))
  }
}

onUnmounted(() => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
  }
  
  if (ws) {
    try {
      ws.onclose = null
      ws.close()
    } catch {}
  }
  
  if (jmuxerInstance) {
    try {
      jmuxerInstance.destroy()
    } catch {}
  }
})
</script>

<style scoped>
.live-preview-h264 {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-player {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  background: #000;
}

.video-player.clickable {
  cursor: pointer;
}

.status-overlay {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  background: rgba(0, 0, 0, 0.7);
  padding: 8px 12px;
  border-radius: 6px;
  backdrop-filter: blur(4px);
  z-index: 10;
}

.fps-indicator,
.latency-indicator {
  color: var(--success-color);
  font-size: 12px;
  font-weight: 600;
  font-family: 'Consolas', 'Monaco', monospace;
}

.latency-indicator {
  color: var(--primary-color);
}

.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
  color: white;
  z-index: 20;
}

.loading-overlay p {
  margin-top: 16px;
  font-size: 14px;
}

/* 加载动画 */
.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Debug Panel Styles */
.debug-toggle {
  margin-left: 8px;
}

.debug-overlay {
  position: absolute;
  top: 60px;
  right: 12px;
  background: rgba(0, 0, 0, 0.9);
  border: 1px solid #444;
  border-radius: 8px;
  padding: 12px;
  min-width: 180px;
  z-index: 30;
  font-size: 12px;
}

.debug-title {
  font-weight: 600;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #444;
  color: #fff;
}

.debug-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  color: #ccc;
}

.debug-row .good {
  color: #67C23A;
}

.debug-row .warn {
  color: #E6A23C;
}

.debug-row .bad {
  color: #F56C6C;
}

.debug-overlay .el-button {
  width: 100%;
  margin-top: 8px;
}
</style>
