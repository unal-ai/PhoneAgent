<template>
  <div class="tasks-page">
    <!-- 统一导航栏 -->
    <TopNavigation />

    <!-- 统一页面头部 -->
    <PageHeader title="任务列表" subtitle="查看和管理所有执行任务">
      <template #actions>
        <el-button 
          v-if="selectedTaskIds.length > 0" 
          type="danger" 
          @click="batchDeleteTasks"
          :icon="Delete"
        >
          删除选中 ({{ selectedTaskIds.length }})
        </el-button>
        <el-button @click="refresh" :icon="Refresh" circle :loading="taskStore.loading" />
      </template>
    </PageHeader>

    <div class="page-container">
      <!-- 筛选器 -->
      <el-card class="filter-card unified-card" shadow="never">
        <div class="filter-content">
          <el-checkbox 
            v-model="selectAll" 
            :indeterminate="isIndeterminate"
            @change="handleSelectAll"
          >
            全选
          </el-checkbox>
          <el-radio-group v-model="filterStatus" @change="handleFilterChange">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="pending">等待中</el-radio-button>
            <el-radio-button label="running">运行中</el-radio-button>
            <el-radio-button label="completed">已完成</el-radio-button>
            <el-radio-button label="failed">失败</el-radio-button>
            <el-radio-button label="cancelled">已取消</el-radio-button>
          </el-radio-group>
        </div>
      </el-card>

      <!-- 任务列表 -->
      <div class="tasks-list" v-loading="taskStore.loading">
      <el-empty
        v-if="tasks.length === 0 && !taskStore.loading"
        description="暂无任务"
      />

      <el-card
        v-for="task in tasks"
        :key="task.task_id"
        class="task-item list-item-card"
        :class="{ selected: selectedTaskIds.includes(task.task_id) }"
        shadow="never"
      >
        <div class="task-header">
          <div class="task-header-left">
            <el-checkbox 
              v-model="selectedTaskIds" 
              :label="task.task_id"
              @click.stop
            />
            <el-tag :type="getStatusType(task.status)" size="small">
              {{ getStatusText(task.status) }}
            </el-tag>
            <span class="task-id-link" @click.stop="showTaskDetail(task)" :title="'点击查看详情: ' + task.task_id">
              {{ task.task_id.substring(0, 8) }}...
            </span>
          </div>
          <span class="task-time">{{ formatTime(task.created_at) }}</span>
        </div>

        <div class="task-instruction clickable" @click="showTaskDetail(task)">
          {{ task.instruction }}
          <el-icon class="view-detail-icon"><ArrowRight /></el-icon>
        </div>

        <div class="task-footer">
          <div class="task-meta-group">
            <div class="task-meta">
              <el-icon><Cellphone /></el-icon>
              <span>{{ task.device_id || '自动分配' }}</span>
            </div>
            
            <div class="task-meta" v-if="task.duration">
              <el-icon><Timer /></el-icon>
              <span>{{ task.duration.toFixed(1) }}s</span>
            </div>

            <div class="task-meta" v-if="task.total_tokens > 0">
              <el-icon><Coin /></el-icon>
              <span>{{ task.total_tokens }} tokens</span>
            </div>
          </div>

          <div class="task-actions">
            <!-- ✅ pending 和 running 状态都显示取消按钮 -->
            <el-button
              v-if="task.status === 'pending' || task.status === 'running'"
              type="warning"
              size="small"
              @click.stop="cancelTask(task.task_id)"
            >
              取消
            </el-button>
            <!-- ✅ 只有已完成/失败/已取消的任务才显示删除按钮 -->
            <el-button
              v-if="task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'"
              type="danger"
              size="small"
              @click.stop="deleteTask(task.task_id)"
              :icon="Delete"
            >
              删除
            </el-button>
          </div>
        </div>

        <!-- 结果展示 -->
        <div v-if="task.result" class="task-result">
          <el-divider />
          <div class="result-label">执行结果：</div>
          <div class="result-content">{{ task.result }}</div>
        </div>

        <div v-if="task.error" class="task-error">
          <el-divider />
          <div class="error-label">错误信息：</div>
          <div class="error-content">{{ task.error }}</div>
        </div>
      </el-card>
      </div>

      <!-- 任务详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="任务详情"
      width="90%"
      :fullscreen="isMobile"
    >
      <el-tabs v-if="selectedTask" type="border-card">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="任务ID">
              {{ selectedTask.task_id }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(selectedTask.status)">
                {{ getStatusText(selectedTask.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="指令">
              {{ selectedTask.instruction }}
            </el-descriptions-item>
            <el-descriptions-item label="设备">
              {{ selectedTask.device_id || '自动分配' }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatFullTime(selectedTask.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间" v-if="selectedTask.started_at">
              {{ formatFullTime(selectedTask.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间" v-if="selectedTask.completed_at">
              {{ formatFullTime(selectedTask.completed_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="执行时长" v-if="selectedTask.duration">
              {{ selectedTask.duration.toFixed(2) }} 秒
            </el-descriptions-item>
            <el-descriptions-item label="执行步骤">
              {{ taskDetailSteps.length }} 步
            </el-descriptions-item>
            <el-descriptions-item label="Token用量" v-if="selectedTask.total_tokens > 0">
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <span>总计: {{ selectedTask.total_tokens || 0 }}</span>
                <span class="token-detail-text">
                  输入: {{ selectedTask.total_prompt_tokens || 0 }} | 
                  输出: {{ selectedTask.total_completion_tokens || 0 }}
                </span>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="结果" v-if="selectedTask.result">
              {{ selectedTask.result }}
            </el-descriptions-item>
            <el-descriptions-item label="错误" v-if="selectedTask.error">
              <el-text type="danger">{{ selectedTask.error }}</el-text>
            </el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        
        <!-- 执行轨迹（带截图） -->
        <el-tab-pane label="执行轨迹">
          <el-empty v-if="taskDetailSteps.length === 0" description="暂无执行步骤" />
          
          <el-timeline v-else>
            <el-timeline-item
              v-for="(step, index) in taskDetailSteps"
              :key="index"
              :timestamp="formatFullTime(step.timestamp)"
              placement="top"
              :color="step.success ? '#67C23A' : '#F56C6C'"
            >
              <el-card shadow="never" class="step-card">
                <template #header>
                  <div class="step-header">
                    <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                      {{ step.success ? '✓ 成功' : '✗ 失败' }}
                    </el-tag>
                  </div>
                </template>
                
                <!-- 操作描述 -->
                <div class="step-action">
                  <strong>操作：</strong>{{ step.action }}
                </div>
                
                <!-- AI观察 -->
                <div v-if="step.observation" class="step-observation">
                  <strong>AI观察：</strong>{{ step.observation }}
                </div>
                
                <!-- AI决策 -->
                <div v-if="step.thinking" class="step-thinking">
                  <strong>AI决策：</strong>{{ step.thinking }}
                </div>
                
                <!-- 截图 -->
                <div v-if="step.screenshot" class="step-screenshot">
                  <el-image
                    :src="getScreenshotUrl(step.screenshot)"
                    :preview-src-list="[getScreenshotUrl(step.screenshot, 'medium')]"
                    fit="cover"
                    style="width: 200px; height: auto; cursor: pointer;"
                  >
                    <template #error>
                      <div class="image-slot">
                        <el-icon><Picture /></el-icon>
                      </div>
                    </template>
                  </el-image>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Cellphone, Timer, Picture, Delete, Coin, ArrowRight } from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'
import { taskApi } from '@/api'
import TopNavigation from '@/components/TopNavigation.vue'
import PageHeader from '@/components/PageHeader.vue'

const router = useRouter()
const taskStore = useTaskStore()

const filterStatus = ref('')
const detailDialogVisible = ref(false)
const selectedTask = ref(null)
const taskDetailSteps = ref([])  // 任务详细步骤（包含截图）
const selectedTaskIds = ref([])  // 选中的任务ID列表
const selectAll = ref(false)  // 全选状态

// API基础URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

const tasks = computed(() => taskStore.tasks)
const isMobile = computed(() => window.innerWidth < 768)

// 判断是否部分选中（用于显示不确定状态）
const isIndeterminate = computed(() => {
  return selectedTaskIds.value.length > 0 && selectedTaskIds.value.length < tasks.value.length
})

// 刷新列表
async function refresh() {
  await taskStore.fetchTasks({
    status: filterStatus.value || undefined
  })
}

// 筛选器变化
function handleFilterChange() {
  refresh()
}

// 取消任务
async function cancelTask(taskId) {
  try {
    await ElMessageBox.confirm('确定要取消这个任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await taskStore.cancelTask(taskId)
    ElMessage.success('任务已取消')
    refresh()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to cancel task:', error)
    }
  }
}

// 删除单个任务
async function deleteTask(taskId) {
  try {
    await ElMessageBox.confirm('确定要删除这个任务吗？删除后无法恢复。', '警告', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await taskStore.deleteTask(taskId)
    ElMessage.success('任务已删除')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete task:', error)
      ElMessage.error('删除失败：' + (error.message || '未知错误'))
    }
  }
}

// 批量删除任务
async function batchDeleteTasks() {
  if (selectedTaskIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的任务')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedTaskIds.value.length} 个任务吗？删除后无法恢复。`, 
      '批量删除警告', 
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await taskStore.deleteBatchTasks(selectedTaskIds.value)
    ElMessage.success(`成功删除 ${selectedTaskIds.value.length} 个任务`)
    selectedTaskIds.value = []
    selectAll.value = false
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to batch delete tasks:', error)
      ElMessage.error('批量删除失败：' + (error.message || '未知错误'))
    }
  }
}

// 全选/取消全选
function handleSelectAll(val) {
  if (val) {
    selectedTaskIds.value = tasks.value.map(t => t.task_id)
  } else {
    selectedTaskIds.value = []
  }
}

// 显示任务详情
async function showTaskDetail(task) {
  selectedTask.value = task
  detailDialogVisible.value = true
  
  // 获取完整的任务详情（包含步骤）
  try {
    const fullTask = await taskApi.get(task.task_id)
    if (fullTask && fullTask.steps) {
      // steps可能是数组（完整步骤信息）或数字（步骤数）
      if (Array.isArray(fullTask.steps)) {
        taskDetailSteps.value = fullTask.steps
      } else {
        taskDetailSteps.value = []
      }
    } else {
      taskDetailSteps.value = []
    }
  } catch (error) {
    console.error('Failed to load task details:', error)
    taskDetailSteps.value = []
  }
}

// 获取截图URL
function getScreenshotUrl(screenshotPath, size = 'small') {
  if (!screenshotPath) return ''
  
  // 如果是完整URL，直接返回
  if (screenshotPath.startsWith('http://') || screenshotPath.startsWith('https://')) {
    return screenshotPath
  }
  
  // 如果是相对路径（如 screenshots/task_xxx/step_001_small.jpg）
  if (screenshotPath.startsWith('screenshots/')) {
    // 替换尺寸后缀
    const basePath = screenshotPath.replace(/_[a-z]+\.jpg$/, '')
    return `${apiBaseUrl}/api/v1/${basePath}_${size}.jpg`
  }
  
  // 如果只是文件名（如 step_001_small.jpg）
  const fileName = screenshotPath.split('/').pop()
  const baseName = fileName.replace(/_[a-z]+\.jpg$/, '')
  return `${apiBaseUrl}/api/v1/screenshots/${selectedTask.value.task_id}/${baseName}_${size}.jpg`
}

// 状态类型
function getStatusType(status) {
  const typeMap = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return typeMap[status] || 'info'
}

// 状态文本
function getStatusText(status) {
  const textMap = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return textMap[status] || status
}

// 格式化时间（相对时间）
function formatTime(dateString) {
  if (!dateString) return '-'
  
  // 确保时间字符串被正确解析为UTC时间
  // 如果没有时区标识符，手动添加'Z'
  let isoString = dateString
  if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('T')) {
    // 如果格式不是ISO，尝试直接解析
    isoString = dateString
  } else if (!isoString.endsWith('Z') && isoString.includes('T') && !isoString.includes('+')) {
    // 如果是ISO格式但没有时区，添加Z
    isoString = dateString + 'Z'
  }
  
  const date = new Date(isoString)
  const now = new Date()
  const diff = now - date
  
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  
  return date.toLocaleDateString('zh-CN')
}

// 格式化完整时间
function formatFullTime(dateString) {
  if (!dateString) return '-'
  
  // 同样的UTC时间处理
  let isoString = dateString
  if (!isoString.endsWith('Z') && isoString.includes('T') && !isoString.includes('+')) {
    isoString = dateString + 'Z'
  }
  
  return new Date(isoString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

// 生命周期


onMounted(() => {
  refresh()
})
</script>

<style scoped>
.tasks-page {
  min-height: 100vh;
  background: var(--bg-tertiary);
  padding-bottom: 20px;
}

.filter-card {
  margin-bottom: var(--space-lg);
}

.filter-content {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.task-item {
  margin-bottom: var(--space-md);
  transition: all 0.3s ease;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-light);
}

.task-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
}

.task-item.selected {
  border-color: var(--primary-color);
  background: var(--info-bg);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.task-instruction {
  font-size: 15px;
  line-height: 1.6;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: var(--radius-base);
  transition: background-color 0.2s ease;
}

.task-instruction.clickable:hover {
  background-color: var(--info-bg);
}

.task-instruction .view-detail-icon {
  color: var(--el-text-color-secondary);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.task-instruction.clickable:hover .view-detail-icon {
  opacity: 1;
}

.task-id-link {
  font-size: 12px;
  font-family: monospace;
  color: var(--primary-color);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--info-bg);
  transition: all 0.2s ease;
}

.task-id-link:hover {
  background: var(--primary-color);
  color: white;
}

.task-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.task-meta-group {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.task-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.task-result,
.task-error {
  margin-top: 8px;
}

.result-label,
.error-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.result-content {
  font-size: 14px;
  color: var(--el-color-success);
}

.error-content {
  font-size: 14px;
  color: var(--el-color-danger);
}

/* 移动端适配 */
@media (max-width: 768px) {
  .page-header h2 {
    font-size: 16px;
  }
  
  .task-instruction {
    font-size: 14px;
  }
  
  .task-meta {
    font-size: 12px;
  }
}

/* 步骤轨迹样式 */
.step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.step-number {
  font-weight: 600;
  font-size: 14px;
}

.step-action {
  margin-bottom: 12px;
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-small);
}

.step-observation {
  margin-bottom: 12px;
  padding: var(--space-sm);
  background: var(--info-bg);
  border-left: 3px solid var(--primary-color);
}

.step-thinking {
  margin-bottom: 12px;
  padding: var(--space-sm);
  background: var(--success-bg);
  border-left: 3px solid var(--success-color);
}

.step-screenshot {
  margin-top: 12px;
  text-align: center;
}

.image-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 200px;
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  font-size: 30px;
}

/* 新增CSS类 */
.token-detail-text {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>

