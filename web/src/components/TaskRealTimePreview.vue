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
      <div class="steps-stream">
        <el-timeline>
          <el-timeline-item
            v-for="(step, index) in steps"
            :key="index"
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

              <!-- 执行动作 -->
              <div v-if="step.action" class="step-action">
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

              <!-- 截图 -->
              <div v-if="step.screenshot" class="step-screenshot">
                <el-image
                  :src="getScreenshotUrl(step.screenshot)"
                  fit="contain"
                  style="width: 200px; height: auto;"
                  :preview-src-list="[getScreenshotUrl(step.screenshot)]"
                />
              </div>

              <!-- 步骤状态 -->
              <div class="step-footer">
                <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                  {{ step.success ? '✓ 成功' : '✗ 失败' }}
                </el-tag>
                <span v-if="step.duration_ms" class="step-duration">
                  耗时: {{ (step.duration_ms / 1000).toFixed(2) }}s
                </span>
                <span v-if="step.tokens_used" class="step-tokens">
                  Token: {{ step.tokens_used.total_tokens || 0 }}
                </span>
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
    </el-card>

    <el-empty v-else description="暂无正在执行的任务" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, VideoPlay, View, Loading } from '@element-plus/icons-vue'
import { taskApi } from '@/api'

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
const totalTokens = computed(() => {
  return steps.value.reduce((sum, step) => {
    return sum + (step.tokens_used?.total_tokens || 0)
  }, 0)
})

let elapsedTimer = null

// API基础URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

function getScreenshotUrl(path) {
  if (!path) return ''
  return `${apiBaseUrl}/${path}`
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
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

function getStepColor(step) {
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
    
    const stepsData = await taskApi.getSteps(props.taskId)
    
    // Load initial steps (WebSocket will update in real-time)
    if (stepsData.steps && Array.isArray(stepsData.steps)) {
      steps.value = stepsData.steps
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

function startElapsedTimer() {
  if (elapsedTimer) return
  
  elapsedTimer = setInterval(() => {
    if (currentTask.value?.started_at && currentTask.value.status === 'running') {
      const start = new Date(currentTask.value.started_at)
      const now = new Date()
      elapsedTime.value = ((now - start) / 1000).toFixed(0)
    }
  }, 1000)
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
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
      
      // 获取最新步骤
      const stepsData = await taskApi.getSteps(props.taskId)
      if (stepsData.steps && Array.isArray(stepsData.steps)) {
        // 检查是否有新步骤
        if (stepsData.steps.length > steps.value.length) {
          // 标记新步骤（用于动画）
          const newSteps = stepsData.steps.slice(steps.value.length)
          newSteps.forEach(step => {
            step.isNew = true
            setTimeout(() => {
              step.isNew = false
            }, 1000)
          })
          
          steps.value = stepsData.steps
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

onMounted(async () => {
  await loadTask()
  
  // 启动轮询（如果任务正在执行）
  if (currentTask.value && currentTask.value.status === 'running') {
    startPolling()
  }
  
  startElapsedTimer()
})

onUnmounted(() => {
  stopPolling()
  stopElapsedTimer()
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

.step-animating {
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
</style>

