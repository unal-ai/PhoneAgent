<template>
  <div class="task-real-time-preview">
    <el-card v-if="currentTask" shadow="never" class="task-progress-card">
      <template #header>
        <div class="task-header">
          <div class="task-header-left">
            <el-tag :type="getStatusType(currentTask.status)" size="large">
              {{ getStatusText(currentTask.status) }}
            </el-tag>
            <el-tooltip 
              :content="currentTask.instruction" 
              placement="bottom-start"
              :disabled="currentTask.instruction.length <= 50"
            >
              <span class="task-instruction">{{ getTruncatedInstruction(currentTask.instruction) }}</span>
            </el-tooltip>
          </div>
          <el-button
            v-if="currentTask.status === 'running'"
            type="success"
            size="small"
            @click="pauseTask"
            :loading="isPausing"
          >
            暂停
          </el-button>
          <el-button
            v-if="currentTask.status === 'paused'"
            type="primary"
            size="small"
            @click="resumeTask"
            :loading="isResuming"
          >
            继续
          </el-button>
          <el-button
            v-if="currentTask.status === 'running' || currentTask.status === 'paused'"
            type="warning"
            size="small"
            @click="cancelTask"
            :loading="isCancelling"
          >
            取消任务
          </el-button>
        </div>
      </template>

      <!-- 任务步骤实时流 -->
      <div ref="stepsStreamRef" class="steps-stream">
        <el-timeline>
          <el-timeline-item
            v-for="(step, index) in validSteps"
            :key="step.step || index"
            :timestamp="formatTime(step.timestamp)"
            :color="getStepColor(step)"
            placement="top"
          >
            <el-card shadow="never" class="step-card" :class="{ 'step-animating': step.isNew }">
              
              <!-- 思考过程 -->
              <div v-if="step.thinking" class="step-thinking">
                <el-icon><ChatDotRound /></el-icon>
                <strong>思考:</strong>
                <div class="thinking-content">{{ getTruncatedThinking(step.thinking) }}</div>
              </div>

              <!-- 用户干预 (New) -->
              <div v-if="step.action && step.action.action === 'user_input'" class="step-user-input">
                <el-icon><Edit /></el-icon>
                <strong>用户干预:</strong>
                <div class="user-input-content">{{ step.action.message }}</div>
              </div>

              <!-- 执行动作 -->
              <div v-else-if="step.action" class="step-action">
                <el-icon><VideoPlay /></el-icon>
                <strong>动作:</strong>
                <div class="action-content">{{ formatAction(step.action) }}</div>
              </div>

              <!-- 观察结果 -->
              <div v-if="step.observation" class="step-observation">
                <el-icon><View /></el-icon>
                <strong>观察:</strong>
                <div class="observation-content">{{ step.observation }}</div>
              </div>

              <!-- 截图 with click position indicator -->
              <div v-if="step.screenshot || step.screenshot_base64" class="step-screenshot-container">
                <div class="screenshot-wrapper">
                  <el-image
                    :src="step.screenshot_base64 || getScreenshotUrl(step.screenshot)"
                    fit="contain"
                    class="screenshot-image"
                    :preview-src-list="[step.screenshot_base64 || getScreenshotUrl(step.screenshot)]"
                  >
                    <template #error>
                      <el-tag type="info" size="small">[截图加载失败]</el-tag>
                    </template>
                  </el-image>
                  <!-- Click position indicator -->
                  <div 
                    v-if="getClickPosition(step.action)" 
                    class="click-indicator"
                    :style="getClickIndicatorStyle(step.action)"
                    :title="`Click: [${getClickPosition(step.action)?.x}, ${getClickPosition(step.action)?.y}]`"
                  >
                    <div class="click-dot"></div>
                    <div class="click-ring"></div>
                  </div>
                </div>
                <div v-if="getClickPosition(step.action)" class="click-coords">
                  📍 {{ step.action?.action }}: [{{ getClickPosition(step.action)?.x }}, {{ getClickPosition(step.action)?.y }}]
                </div>
              </div>

              <!-- 步骤状态 -->
              <div class="step-footer">
                <el-tag :type="step.success === true ? 'success' : (step.success === false ? 'danger' : 'info')" size="small">
                  {{ step.success === true ? '✓ 成功' : (step.success === false ? '✗ 失败' : '进行中') }}
                </el-tag>
                <span v-if="step.duration_ms" class="step-duration">
                  耗时: {{ (step.duration_ms / 1000).toFixed(2) }}s
                </span>
                <span v-if="step.tokens_used" class="step-tokens">
                  Token: {{ step.tokens_used.total_tokens || 0 }}
                </span>
              </div>
              
              <!-- 失败原因（仅失败时显示） -->
              <div v-if="step.success === false && step.observation" class="step-error-reason">
                <el-icon><WarningFilled /></el-icon>
                <strong>失败原因:</strong>
                <span>{{ step.observation }}</span>
              </div>
            </el-card>
          </el-timeline-item>

          <!-- 加载中指示器 -->
          <el-timeline-item v-if="currentTask.status === 'running'" color="#409eff">
            <div class="loading-indicator">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>执行中...</span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <!-- 任务统计 -->
      <el-divider />
      <div class="task-stats">
        <el-statistic title="已执行步骤" :value="steps.length" />
        <el-statistic title="总Token消耗" :value="totalTokens" />
        <el-statistic 
          v-if="currentTask.started_at" 
          title="已用时" 
          :value="elapsedTime" 
          suffix="秒"
        />
      </div>

      <!-- 用户干预输入 -->
      <el-divider v-if="currentTask.status === 'running'" />
      <div v-if="currentTask.status === 'running'" class="inject-section">
        <div class="inject-header">
          <el-icon><Edit /></el-icon>
          <span>用户干预</span>
          <el-tooltip content="输入的内容会作为[User Intervention]添加到AI上下文，在下一步生效">
            <el-icon><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="inject-input-row">
          <el-input
            v-model="injectComment"
            type="textarea"
            :rows="2"
            placeholder="输入干预指令，例如：点击返回按钮、不要点击广告..."
            :disabled="isInjecting"
            maxlength="200"
            show-word-limit
          />
          <el-button
            type="primary"
            :loading="isInjecting"
            :disabled="!injectComment.trim()"
            @click="handleInject"
            class="inject-button"
          >
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
        </div>
      </div>

      <!-- Debug 面板（折叠） -->
      <el-divider />
      <el-collapse v-model="activeDebugPanel">
        <el-collapse-item title="🔍 调试面板 - LLM上下文" name="debug">
          <div class="debug-panel">
            <div class="debug-actions">
              <el-button size="small" @click="loadContext" :loading="isLoadingContext">
                <el-icon><Refresh /></el-icon>
                刷新上下文
              </el-button>
              <el-tag type="info" size="small">
                消息数: {{ contextMessages.length }}
              </el-tag>
            </div>
            <div v-if="contextMessages.length === 0" class="debug-empty">
              <el-empty description="点击刷新获取LLM上下文" :image-size="60" />
            </div>
            <div v-else class="context-messages">
              <div 
                v-for="(msg, idx) in contextMessages" 
                :key="idx" 
                class="context-message"
                :class="msg.role"
              >
                <div class="message-header">
                  <el-tag :type="getRoleType(msg.role)" size="small">
                    {{ getRoleName(msg.role) }}
                  </el-tag>
                  <span class="message-index">#{{ idx + 1 }}</span>
                </div>
                <div class="message-content">
                  <template v-if="typeof msg.content === 'string'">
                    <pre class="full-content">{{ msg.content }}</pre>
                  </template>
                  <template v-else-if="Array.isArray(msg.content)">
                    <div v-for="(item, i) in msg.content" :key="i" class="content-item">
                      <pre v-if="item.type === 'text'" class="full-content">{{ item.text }}</pre>
                      <div v-else-if="item.type === 'image_url'" class="context-image-indicator">
                        <el-tag type="success" size="small">
                          <el-icon><Picture /></el-icon>
                          Screenshot ({{ getImageSize(item.image_url?.url) }})
                        </el-tag>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-empty v-else description="暂无正在执行的任务" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, VideoPlay, View, Loading, Edit, QuestionFilled, Promotion, Refresh, WarningFilled, Picture } from '@element-plus/icons-vue'
import { taskApi, request } from '@/api'

const props = defineProps({
  taskId: {
    type: String,
    default: null
  }
})

const currentTask = ref(null)
const steps = ref([])
const isCancelling = ref(false)
const elapsedTime = ref(0)
const pollingTimer = ref(null)
const pollingInterval = 1000 // Polling interval in ms
const stepsStreamRef = ref(null) // Ref for auto-scroll

// Inject comment state
const injectComment = ref('')
const isInjecting = ref(false)

// Debug panel state
const activeDebugPanel = ref([])
const contextMessages = ref([])
const isLoadingContext = ref(false)

const totalTokens = computed(() => {
  return steps.value.reduce((sum, step) => {
    return sum + (step?.tokens_used?.total_tokens || 0)
  }, 0)
})

// Filter out invalid steps to prevent rendering errors
const validSteps = computed(() => {
  return steps.value.filter(step => step && typeof step === 'object')
})

let elapsedTimer = null

// API基础URL（剔除 /api 或 /api/v1 以便访问静态截图）
const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

function normalizeApiBaseUrl(baseUrl) {
  if (!baseUrl) return ''

  // 兼容结尾带 /api 或 /api/v1 的配置，静态文件挂载在根路径
  return baseUrl
    .replace(/\/?api\/?v1\/?$/, '')
    .replace(/\/?api\/?$/, '')
    .replace(/\/+$/, '') // 去除多余的斜杠
}

const apiBaseUrl = normalizeApiBaseUrl(rawApiBaseUrl)

function getScreenshotUrl(path) {
  if (!path) return ''
  
  // Absolute URL
  if (path.startsWith('http')) return path
  
  // Case 2: data/screenshots/... prefix (from backend)
  // Backend returns: data/screenshots/{task_id}/{filename}
  // Frontend mount: /screenshots -> data/screenshots
  // So we need to strip "data/" prefix
  if (path.startsWith('data/screenshots/')) {
      const relativePath = path.substring(5) // remove "data/"
      return `${apiBaseUrl}/${relativePath}`
  }

  // Case 3: Relative path (already contains screenshots/...)
  if (path.startsWith('screenshots/')) {
      return `${apiBaseUrl}/${path}`
  }
  
  // Filename only (construct full path using taskId)
  // Ensure we have a task ID to construct the path
  const taskId = props.taskId || currentTask.value?.task_id
  if (taskId) {
      return `${apiBaseUrl}/screenshots/${taskId}/${path}`
  }
  
  // Fallback
  return `${apiBaseUrl}/${path}`
}

// Get approximate image size from base64 data URL
function getImageSize(dataUrl) {
  if (!dataUrl) return '?'
  if (!dataUrl.startsWith('data:')) return 'file'
  
  // Calculate approximate size from base64 length
  // Base64 is ~33% larger than binary, and we subtract the header
  const base64Part = dataUrl.split(',')[1] || ''
  const sizeBytes = Math.floor(base64Part.length * 0.75)
  
  if (sizeBytes < 1024) return `${sizeBytes}B`
  if (sizeBytes < 1024 * 1024) return `${Math.floor(sizeBytes / 1024)}KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)}MB`
}

// Extract click position from action (coordinates are 0-1000 relative)
function getClickPosition(action) {
  if (!action) return null

  const actionType = action.action

  // Actions with direct coordinates
  if (['Tap', 'Double Tap', 'Long Press'].includes(actionType)) {
    const coordinates = action.coordinates || action.coords
    if (coordinates && Array.isArray(coordinates) && coordinates.length >= 2) {
      return { x: coordinates[0], y: coordinates[1] }
    }

    const element = action.element
    if (element && Array.isArray(element) && element.length >= 2) {
      return { x: element[0], y: element[1] }
    }
  }

  // Swipe has start/end
  if (actionType === 'Swipe') {
    const start = action.start
    if (start && Array.isArray(start) && start.length >= 2) {
      return { x: start[0], y: start[1], isSwipeStart: true }
    }
  }

  return null
}

// Calculate CSS style for click indicator position
// Image is 200px wide, coordinates are 0-1000 relative
function getClickIndicatorStyle(action) {
  const pos = getClickPosition(action)
  if (!pos) return {}
  
  // Convert 0-1000 coordinates to percentage
  const leftPercent = pos.x / 10
  const topPercent = pos.y / 10
  
  return {
    left: `${leftPercent}%`,
    top: `${topPercent}%`
  }
}

// 截断指令文本，适合在标题中显示
function getTruncatedInstruction(instruction) {
  if (!instruction) return ''
  const maxLength = 50 // 最多显示50个字符
  if (instruction.length <= maxLength) {
    return instruction
  }
  return instruction.substring(0, maxLength) + '...'
}

// 截断思考内容，避免过长
function getTruncatedThinking(thinking) {
  if (!thinking) return ''
  const maxLength = 200 // 最多显示200个字符
  if (thinking.length <= maxLength) {
    return thinking
  }
  return thinking.substring(0, maxLength) + '...'
}

// 格式化action显示
function formatAction(action) {
  if (!action) return ''
  
  // 如果已经是字符串，直接返回
  if (typeof action === 'string') {
    return action
  }
  
  // 如果是对象，格式化为易读字符串
  if (typeof action === 'object') {
    try {
      // 提取关键信息
      const actionType = action.action || action.type || 'Unknown'
      const details = []
      
      for (const [key, value] of Object.entries(action)) {
        if (key !== 'action' && key !== 'type' && key !== '_metadata') {
          details.push(`${key}: ${JSON.stringify(value)}`)
        }
      }
      
      if (details.length > 0) {
        return `${actionType} - ${details.join(', ')}`
      }
      return actionType
    } catch (e) {
      // 降级：直接JSON化
      return JSON.stringify(action, null, 2)
    }
  }
  
  return String(action)
}

function getStatusType(status) {
  const types = {
    pending: 'info',
    running: 'warning',
    paused: 'info',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = {
    pending: '等待中',
    running: '执行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

function getStepColor(step) {
  if (step.status === 'user_input') return '#8e44ad' // Purple for user input
  if (step.success === undefined) return '#409eff'
  return step.success ? '#67c23a' : '#f56c6c'
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN')
}

async function loadTask() {
  if (!props.taskId) {
    return
  }
  
  try {
    currentTask.value = await taskApi.get(props.taskId)
    console.log('[TaskPreview] Loaded task:', currentTask.value?.task_id, 'status:', currentTask.value?.status)
    
    // Use steps from task object directly
    if (currentTask.value?.steps && Array.isArray(currentTask.value.steps)) {
      steps.value = currentTask.value.steps
      console.log('[TaskPreview] Set steps.value, now has', steps.value.length, 'steps')
    }
  } catch (error) {
    console.error('[TaskPreview] Failed to load task:', error)
  }
}

async function cancelTask() {
  if (!currentTask.value) return
  
  isCancelling.value = true
  try {
    await taskApi.cancel(currentTask.value.task_id)
    ElMessage.success('任务已取消')
    currentTask.value.status = 'cancelled'
  } catch (error) {
    ElMessage.error('取消任务失败: ' + error.message)
  } finally {
    isCancelling.value = false
  }
}

// 🆕 暂停/恢复功能
const isPausing = ref(false)
const isResuming = ref(false)

async function pauseTask() {
  if (!currentTask.value) return
  
  isPausing.value = true
  try {
    await request.post(`/tasks/${currentTask.value.task_id}/pause`)
    ElMessage.success('任务已暂停')
    currentTask.value.status = 'paused'
  } catch (error) {
    ElMessage.error('暂停失败: ' + error.message)
  } finally {
    isPausing.value = false
  }
}

async function resumeTask() {
  if (!currentTask.value) return
  
  isResuming.value = true
  try {
    await request.post(`/tasks/${currentTask.value.task_id}/resume`)
    ElMessage.success('任务继续执行')
    currentTask.value.status = 'running'
  } catch (error) {
    ElMessage.error('恢复失败: ' + error.message)
  } finally {
    isResuming.value = false
  }
}

function startElapsedTimer() {
  if (elapsedTimer) return
  
  elapsedTimer = setInterval(() => {
    if (currentTask.value?.started_at && currentTask.value.status === 'running') {
      const start = new Date(currentTask.value.started_at)
      const now = new Date()
      elapsedTime.value = Math.floor((now - start) / 1000)
    }
  }, 1000)
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

// Auto-scroll to bottom when new steps arrive
function scrollToBottom() {
  nextTick(() => {
    if (stepsStreamRef.value) {
      stepsStreamRef.value.scrollTop = stepsStreamRef.value.scrollHeight
    }
  })
}

// Handle user comment injection
async function handleInject() {
  if (!injectComment.value.trim() || !props.taskId) return
  
  isInjecting.value = true
  try {
    await taskApi.inject(props.taskId, injectComment.value.trim())
    ElMessage.success('干预指令已发送，将在下一步生效')
    injectComment.value = ''
  } catch (error) {
    ElMessage.error('发送失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isInjecting.value = false
  }
}

// Load LLM context for debugging
async function loadContext() {
  if (!props.taskId) return
  
  isLoadingContext.value = true
  try {
    const result = await taskApi.getContext(props.taskId)
    contextMessages.value = result.context || []
  } catch (error) {
    // Only show error if not a "not found" error for completed tasks
    if (!error.response?.data?.detail?.includes('not found')) {
      ElMessage.error('获取上下文失败: ' + (error.response?.data?.detail || error.message))
    }
    contextMessages.value = []
  } finally {
    isLoadingContext.value = false
  }
}

// Auto-refresh context when debug panel is opened
let contextRefreshTimer = null

watch(activeDebugPanel, (newVal) => {
  if (newVal && newVal.length > 0) {
    // Panel opened - load immediately and start auto-refresh
    loadContext()
    if (!contextRefreshTimer && currentTask.value?.status === 'running') {
      contextRefreshTimer = setInterval(loadContext, 3000)
    }
  } else {
    // Panel closed - stop auto-refresh
    if (contextRefreshTimer) {
      clearInterval(contextRefreshTimer)
      contextRefreshTimer = null
    }
  }
})

// Helper: Get role display type
function getRoleType(role) {
  const types = {
    system: 'warning',
    user: 'primary',
    assistant: 'success'
  }
  return types[role] || 'info'
}

// Helper: Get role display name
function getRoleName(role) {
  const names = {
    system: '系统',
    user: '用户',
    assistant: 'AI'
  }
  return names[role] || role
}

// Helper: Truncate content for display
function truncateContent(content, maxLen = 300) {
  if (!content) return ''
  if (content.length <= maxLen) return content
  return content.substring(0, maxLen) + '...'
}

// Start polling for task updates
function startPolling() {
  if (pollingTimer.value) return
  
  pollingTimer.value = setInterval(async () => {
    if (!props.taskId) {
      stopPolling()
      return
    }
    
    try {
      // 获取最新任务数据
      const task = await taskApi.get(props.taskId)
      
      // 更新任务状态
      if (currentTask.value) {
        currentTask.value.status = task.status
        currentTask.value.result = task.result
        currentTask.value.error = task.error
      }
      
      // Update steps from task object directly
      if (task.steps && Array.isArray(task.steps)) {
        task.steps.forEach((newStep, index) => {
          // If this step index is beyond our current length, it's a new step
          if (index >= steps.value.length) {
            steps.value.push(newStep)
            // Auto-scroll to show new steps
            scrollToBottom()
          } else {
             // Existing step - merge carefully
             const currentStep = steps.value[index]
             
             // Check if we should preserve local thinking (streaming buffer)
             // We keep local thinking if:
             // 1. New step is NOT completed/failed yet (still running)
             // 2. AND local thinking is longer than new thinking
             // 3. AND it's generally the same step content (optional check, but good for safety)
             const shouldPreserveThinking = 
               (newStep.status !== 'completed' && newStep.status !== 'failed') && 
               (currentStep.thinking && currentStep.thinking.length > (newStep.thinking || "").length)
             
             const mergedStep = { ...newStep }
             
             if (shouldPreserveThinking) {
                mergedStep.thinking = currentStep.thinking
             }
             
             // Update the step in place
             steps.value.splice(index, 1, mergedStep)
          }
        })
        
        // If server has fewer steps (rare, maybe cancelled/reset?), truncate local
        if (task.steps.length < steps.value.length) {
            steps.value = task.steps
        }
      }
      
      // 任务完成后停止轮询
      if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
        stopPolling()
        stopElapsedTimer()
      }
    } catch (error) {
      console.error('[TaskPreview] Polling error:', error)
    }
  }, pollingInterval)
}

// Stop polling
function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

// Watch taskId changes, reload task automatically
watch(() => props.taskId, async (newTaskId, oldTaskId) => {
  // Stop old task polling
  stopPolling()
  
  if (newTaskId && newTaskId !== oldTaskId) {
    // 清空旧数据
    steps.value = []
    elapsedTime.value = 0
    // 加载新任务
    await loadTask()
    // 重启计时器
    stopElapsedTimer()
    startElapsedTimer()
    
    // Start new task polling
    if (currentTask.value && currentTask.value.status === 'running') {
      startPolling()
    }
  }
}, { immediate: false })


// Real-time Event Handlers

function handleStreamToken(event) {
  const data = event.detail
  if (data.task_id !== props.taskId) return
  
  // Find current step to update
  // Usually it's the last step
  if (steps.value.length === 0) {
    // Should have been initialized by task_step_update or initial load
    return
  }
  
  const lastStep = steps.value[steps.value.length - 1]
  
  // Update thinking content
  if (!lastStep.thinking) {
    lastStep.thinking = ''
  }
  
  lastStep.thinking += data.token
  
  // Auto-scroll on new content
  scrollToBottom()
}

function handleTaskStepUpdate(event) {
  const data = event.detail
  if (data.task_id !== props.taskId) return
  
  const stepIndex = data.step
  
  // Find existing step or append new one
  const existingStepIndex = steps.value.findIndex(s => s.step === stepIndex || s.step_index === stepIndex)
  
  if (existingStepIndex !== -1) {
    // Update existing step
    const step = steps.value[existingStepIndex]
    
    // Preserve existing thinking if it's more complete (from streaming)
    // unless the update provides a full new thinking string
    const newThinking = data.thinking || ''
    const currentThinking = step.thinking || ''
    
    // Merge data
    Object.assign(step, {
      ...data,
      // If new thinking is shorter than current (and we were streaming), keep current
      // This prevents "flicker" if the update event happens to carry partial data
      // BUT if it's a completion event, we should trust it
      thinking: (data.status === 'completed' || newThinking.length > currentThinking.length) 
        ? newThinking 
        : currentThinking
    })
  } else {
    // New step
    steps.value.push(data)
    scrollToBottom()
  }
}

// Function to handle task status changes (e.g. completion)
function handleTaskStatusChange(event) {
  const data = event.detail
  if (data.task_id !== props.taskId) return
  
  if (currentTask.value) {
    currentTask.value.status = data.status
    if (data.message) currentTask.value.result = data.message
    if (data.error) currentTask.value.error = data.error
    
    // Stop polling if done
    if (['completed', 'failed', 'cancelled'].includes(data.status)) {
      stopPolling()
      stopElapsedTimer()
    }
  }
}

onMounted(async () => {
  await loadTask()
  
  // 启动轮询（作为兜底 sync）
  if (currentTask.value && currentTask.value.status === 'running') {
    startPolling()
  }
  
  startElapsedTimer()
  
  // Add Event Listeners
  window.addEventListener('stream-token', handleStreamToken)
  window.addEventListener('task-step-update', handleTaskStepUpdate)
  window.addEventListener('task-status-change', handleTaskStatusChange)
})

onUnmounted(() => {
  stopPolling()
  stopElapsedTimer()
  // Cleanup context refresh timer
  if (contextRefreshTimer) {
    clearInterval(contextRefreshTimer)
    contextRefreshTimer = null
  }
  
  // Remove Event Listeners
  window.removeEventListener('stream-token', handleStreamToken)
  window.removeEventListener('task-step-update', handleTaskStepUpdate)
  window.removeEventListener('task-status-change', handleTaskStatusChange)
})
</script>

<style scoped>
.task-real-time-preview {
  height: 100%;
  overflow-y: auto;
}

/* 主卡片样式 - 与Home.vue统一 */
.task-progress-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-light);
  transition: all 0.3s ease;
}

.task-progress-card:hover {
  box-shadow: var(--shadow-base);
}

.task-progress-card :deep(.el-card__header) {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-lg);
  border-radius: var(--radius-large) var(--radius-large) 0 0;
  min-height: 68px;
  height: 68px;
  display: flex;
  align-items: center;
}

.debug-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.full-content {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  font-family: monospace;
  font-size: 12px;
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 12px;
}

.task-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0; /* 允许子元素收缩 */
}

.task-instruction {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.steps-stream {
  max-height: 600px;
  overflow-y: auto;
  padding: 12px 0;
}

/* 步骤卡片样式 - 统一边框和圆角 */
.step-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: none;
  transition: all 0.3s ease;
}

.step-card:hover {
  border-color: var(--border-base);
}

.step-number {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: var(--space-sm);
}

.step-thinking,
.step-action,
.step-observation {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: var(--radius-base);
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.step-thinking {
  background: var(--info-bg);
  border-left: 3px solid var(--primary-color);
}

.step-action {
  background: var(--success-bg);
  border-left: 3px solid var(--success-color);
}

.step-observation {
  background: var(--error-bg);
  border-left: 3px solid var(--error-color);
}

.step-user-input {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: var(--radius-base);
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #f3e5f5; /* Light purple */
  border-left: 3px solid #8e44ad; /* Purple */
}

.user-input-content {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-word;
  font-weight: 500;
  color: #8e44ad;
}

.thinking-content,
.action-content,
.observation-content {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-word;
}

.step-screenshot {
  margin-top: 12px;
  text-align: center;
}

.step-footer {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.step-duration,
.step-tokens {
  padding: 2px 8px;
  background: var(--bg-secondary);
  border-radius: var(--radius-small);
  border: 1px solid var(--border-light);
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--primary-color);
}

/* Animation removed as per user request */
/* .step-animating {
  animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
} */

/* Error reason display */
.step-error-reason {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--danger-bg, #fef0f0);
  border-left: 3px solid var(--danger-color, #f56c6c);
  border-radius: 4px;
  font-size: 13px;
  color: var(--danger-color, #f56c6c);
}

.step-error-reason .el-icon {
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 2px;
}

.step-error-reason strong {
  flex-shrink: 0;
}

.task-stats {
  display: flex;
  justify-content: space-around;
  gap: 24px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .task-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .task-header-left {
    width: 100%;
  }
  
  .steps-stream {
    max-height: 400px;
  }
}

/* Inject Section */
.inject-section {
  padding: 12px 0;
}

.inject-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.inject-input-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.inject-input-row .el-textarea {
  flex: 1;
}

.inject-button {
  height: 60px;
  min-width: 80px;
}

/* Debug Panel */
.debug-panel {
  padding: 12px 0;
}

.debug-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.debug-empty {
  padding: 20px 0;
}

.context-messages {
  max-height: 400px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.context-message {
  padding: 12px;
  border-radius: var(--radius-base);
  border: 1px solid var(--border-light);
}

.context-message.system {
  background: var(--warning-bg);
  border-left: 3px solid var(--warning-color);
}

.context-message.user {
  background: var(--info-bg);
  border-left: 3px solid var(--primary-color);
}

.context-message.assistant {
  background: var(--success-bg);
  border-left: 3px solid var(--success-color);
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.message-index {
  font-size: 12px;
  color: var(--text-tertiary);
}

.message-content {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
}

.content-item {
  margin-bottom: 4px;
}

/* Screenshot with click position indicator */
.step-screenshot-container {
  margin-top: 10px;
}

.screenshot-wrapper {
  position: relative;
  display: inline-block;
  width: 200px;
}

.screenshot-image {
  width: 200px;
  height: auto;
}

.click-indicator {
  position: absolute;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 10;
}

.click-dot {
  width: 8px;
  height: 8px;
  background: #ff4444;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 4px rgba(0,0,0,0.5);
}

.click-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 20px;
  height: 20px;
  border: 2px solid #ff4444;
  border-radius: 50%;
  animation: click-pulse 1s ease-out infinite;
}

@keyframes click-pulse {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(2);
    opacity: 0;
  }
}

.click-coords {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>

