<template>
  <div class="home-page">
    <!-- 统一导航栏 -->
    <TopNavigation />

    <!-- 主内容区 - 三栏布局 -->
    <div class="main-content">
      <div class="content-grid three-column">
        <!-- 左侧：任务创建 -->
        <div class="left-panel">
          <el-card class="task-card unified-card" shadow="never">
            <template #header>
              <div class="card-header-unified">
                <div class="card-title-content">
                  <span class="card-title-text">创建任务</span>
                </div>
                <div class="card-actions">
                  <el-tag type="info" size="small">AI 自动化</el-tag>
                </div>
              </div>
            </template>

            <el-form :model="taskForm" label-position="top" class="task-form">
              <!-- 执行模式选择 -->
              <el-form-item label="执行模式">
                <el-radio-group v-model="taskForm.execution_mode" @change="handleModeChange">
                  <el-radio-button value="step_by_step">
                    <el-icon><Position /></el-icon>
                    逐步执行（推荐）
                  </el-radio-button>
                  <el-radio-button value="planning">
                    <el-icon><Lightning /></el-icon>
                    智能规划（⚠️ Beta - 不稳定）
                  </el-radio-button>
                </el-radio-group>
                <div class="mode-description">
                  <div v-if="taskForm.execution_mode === 'step_by_step'" class="mode-hint mode-hint-success">
                    <el-icon><InfoFilled /></el-icon>
                    ✅ 推荐：AI每步思考并决策，稳定性高，适合所有任务
                  </div>
                  <div v-else class="mode-hint mode-hint-warning">
                    <el-icon><InfoFilled /></el-icon>
                    ⚠️ 警告：规划模式仍在实验阶段，成功率较低，不建议生产环境使用，仅适合简单任务测试
                  </div>
                </div>
              </el-form-item>

              <!-- 任务指令输入 -->
              <el-form-item label="任务指令">
                <el-input
                  v-model="taskForm.instruction"
                  type="textarea"
                  :rows="4"
                  placeholder="描述你想让手机执行的任务，例如：打开微信，给张三发送消息"
                  maxlength="500"
                  show-word-limit
                  clearable
                />
              </el-form-item>
              
              <!-- 规划模式专属选项 🆕 -->
              <div v-if="taskForm.execution_mode === 'planning'" class="planning-options">
                <el-form-item label="计划预览">
                  <el-switch
                    v-model="taskForm.preview_plan"
                    active-text="生成后先预览再执行"
                    inactive-text="直接生成并执行"
                  />
                  <div class="form-hint-text">
                    💡 开启后可以查看和编辑AI生成的计划，确认无误后再执行
                  </div>
                </el-form-item>
              </div>

              <!-- 设备选择和操作按钮（一行显示） -->
              <el-form-item label="选择设备">
                <div class="device-action-row">
                  <!-- 设备选择器 -->
                  <el-select
                    v-model="taskForm.device_id"
                    placeholder="请选择设备"
                    class="device-selector"
                    clearable
                    popper-class="home-device-select-dropdown"
                  >
                    <el-option
                      v-for="device in availableDevices"
                      :key="device.device_id"
                      :label="device.device_name || device.device_id"
                      :value="device.device_id"
                    >
                      <div class="home-device-option">
                        <div class="home-device-option-left">
                          <span class="home-device-name">{{ device.device_name || device.device_id }}</span>
                        </div>
                        <div class="home-device-option-right">
                          <el-tag :type="getDeviceStatusType(device)" size="small">
                            {{ getDeviceStatusText(device) }}
                          </el-tag>
                          <el-tooltip v-if="device.frp_connected && !device.ws_connected" content="FRP已连接，WebSocket未连接">
                            <el-tag type="warning" size="small">部分连接</el-tag>
                          </el-tooltip>
                        </div>
                      </div>
                    </el-option>
                    <template v-if="availableDevices.length === 0">
                      <el-option disabled value="" label="暂无可用设备" />
                    </template>
                  </el-select>

                  <!-- 创建任务按钮 -->
                  <el-button
                    type="primary"
                    @click="handleCreateTask"
                    :loading="isCreatingTask"
                    :disabled="!taskForm.instruction.trim() || !taskForm.device_id"
                    class="create-task-button"
                  >
                    <el-icon><VideoPlay /></el-icon>
                    {{ isCreatingTask ? '创建中...' : '创建并执行任务' }}
                  </el-button>

                  <!-- 语音输入按钮 -->
                  <el-tooltip content="语音输入任务指令" placement="top">
                    <el-button
                      :type="isRecording ? 'danger' : 'info'"
                      circle
                      @click="toggleRecording"
                      :loading="isTranscribing"
                      :disabled="isTranscribing"
                      class="voice-input-button"
                    >
                      <el-icon v-if="!isTranscribing">
                        <Microphone v-if="!isRecording" />
                        <VideoPause v-else />
                      </el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </el-form-item>

              <!-- 提示词卡片 -->
              <el-divider content-position="left">
                <el-icon><Memo /></el-icon>
                提示词卡片
                <el-button
                  type="primary"
                  text
                  size="small"
                  @click="showPromptCardsManager"
                  :icon="Setting"
                  class="manage-prompt-button"
                >
                  管理
                </el-button>
              </el-divider>
              <div class="prompt-cards-section">
                <el-switch
                  v-model="promptCardsEnabled"
                  active-text="启用"
                  inactive-text="不启用"
                  class="prompt-cards-switch"
                />
                <div v-if="promptCardsEnabled" class="prompt-cards-display" v-loading="loadingPromptCards">
                  <div class="prompt-cards-grid">
                    <div
                      v-for="card in displayPromptCards"
                      :key="card.id"
                      @click="togglePromptCard(card.id)"
                      class="prompt-card-item"
                      :class="{ 'selected': taskForm.prompt_card_ids.includes(card.id) }"
                    >
                      <div class="card-header-mini">
                        <span class="card-title-mini">{{ getCategoryIcon(card.category) }} {{ card.title }}</span>
                        <el-tag size="small" :type="card.is_system ? 'info' : 'success'">
                          {{ card.category }}
                        </el-tag>
                      </div>
                      <p class="card-description-mini">{{ card.description }}</p>
                      <div class="card-selection-indicator">
                        <el-icon v-if="taskForm.prompt_card_ids.includes(card.id)"><CircleCheck /></el-icon>
                      </div>
                    </div>
                  </div>
                  <div class="selected-cards-summary" v-if="selectedPromptCards.length > 0">
                    已选择 {{ selectedPromptCards.length }} 个提示词卡片：
                    <el-tag
                      v-for="card in selectedPromptCards"
                      :key="card.id"
                      size="small"
                      type="info"
                      class="selected-card-tag"
                      closable
                      @close="removePromptCard(card.id)"
                    >
                      {{ card.title }}
                    </el-tag>
                  </div>
                </div>
              </div>

              <!-- 快捷指令 -->
              <el-divider content-position="left">
                <el-icon><Lightning /></el-icon>
                快捷指令
                <el-button
                  type="primary"
                  text
                  size="small"
                  @click="showShortcutsManager"
                  :icon="Setting"
                  class="manage-prompt-button"
                >
                  管理
                </el-button>
              </el-divider>
              <div class="shortcuts-section" v-loading="loadingShortcuts">
                <div class="shortcuts-grid">
                  <div
                    v-for="shortcut in displayShortcuts"
                    :key="shortcut.id"
                    @click="useShortcut(shortcut)"
                    class="shortcut-card-item"
                  >
                    <div class="shortcut-header-mini">
                      <span class="shortcut-title-mini">{{ getCategoryIcon(shortcut.category) }} {{ shortcut.title }}</span>
                      <el-tag size="small" :type="shortcut.is_system ? 'info' : 'success'">
                        {{ shortcut.category }}
                      </el-tag>
                    </div>
                    <p class="shortcut-description-mini">{{ shortcut.instruction }}</p>
                  </div>
                </div>
              </div>

              <!-- 录音状态指示器 -->
              <div v-if="isRecording" class="recording-indicator">
                <el-icon class="recording-icon animate-pulse"><Microphone /></el-icon>
                <span>正在录音... {{ recordingTime }}s</span>
              </div>
              
              <!-- 识别状态指示器 -->
              <div v-if="isTranscribing" class="transcribing-indicator">
                <el-icon class="loading-icon"><Loading /></el-icon>
                <span>{{ transcriptionProgress }}</span>
              </div>

              <!-- 高级设置 -->
              <el-collapse class="advanced-settings-collapse">
                <el-collapse-item name="advanced">
                  <template #title>
                    <div class="advanced-settings-title">
                      <el-icon><Setting /></el-icon> ⚙️ 高级设置
                    </div>
                  </template>
                  <el-form-item label="最大步骤数">
                    <el-input-number v-model="taskForm.max_steps" :min="10" :max="300" :step="10" />
                    <div class="form-hint-text">任务执行的最大步数限制 (默认: 100)</div>
                  </el-form-item>
                  <el-form-item label="历史截图记忆 (Visual Memory)">
                    <el-input-number v-model="taskForm.max_history_images" :min="0" :max="5" />
                    <div class="form-hint-text">保留最近 N 张截图，帮助AI感知界面变化 (0=仅当前, 1=当前+上一步)</div>
                  </el-form-item>
                  
                  <el-divider content-position="left">模型配置 (AI Model)</el-divider>
                  
                  <el-form-item label="AI厂商预设">
                    <el-radio-group v-model="aiProviderPreset" @change="handlePresetChange">
                      <el-radio-button label="default">✅ 服务端默认 (Server Default)</el-radio-button>
                      <el-radio-button label="zhipu">智谱AI</el-radio-button>
                      <el-radio-button label="openai">OpenAI</el-radio-button>
                      <el-radio-button label="local">本地模型 (Local)</el-radio-button>
                      <el-radio-button label="custom">自定义</el-radio-button>
                    </el-radio-group>
                  </el-form-item>

                  <el-form-item label="Base URL">
                    <el-input v-model="taskForm.ai_base_url" placeholder="例如: https://open.bigmodel.cn/api/paas/v4/" />
                    <div class="form-hint-text">API 服务地址 (Base URL)</div>
                  </el-form-item>

                  <el-form-item label="API Key">
                    <el-input 
                      v-model="taskForm.ai_api_key" 
                      type="password" 
                      placeholder="留空则使用服务端环境变量配置" 
                      show-password
                    />
                  </el-form-item>

                  <el-form-item label="模型名称">
                    <el-input v-model="taskForm.ai_model" placeholder="例如: autoglm-phone, glm-4-flash, gpt-4o" />
                    <div class="form-hint-text">推荐: autoglm-phone (官方优化), glm-4-flash (便宜速度快)</div>
                  </el-form-item>

                  <el-form-item>
                    <el-button 
                      type="success" 
                      plain 
                      size="small" 
                      @click="testModelConnection" 
                      :loading="isTestingConnection"
                      :icon="Connection"
                      class="test-connection-btn"
                    >
                      {{ isTestingConnection ? '测试中...' : '测试连接' }}
                    </el-button>
                  </el-form-item>

                </el-collapse-item>
              </el-collapse>
            </el-form>
          </el-card>
        </div>

        <!-- 中间：设备实时预览 -->
        <div class="middle-panel">
          <LivePreview />
        </div>

        <!-- 右侧：任务执行实时预览 -->
        <div class="right-panel">
          <el-card class="task-preview-card unified-card" shadow="never" v-if="!currentTaskId">
            <template #header>
              <div class="card-header-unified">
                <div class="card-title-content">
                  <span class="card-title-text">任务执行进度</span>
                </div>
                <div class="card-actions">
                  <el-tag type="info" size="small">等待中</el-tag>
                </div>
              </div>
            </template>
            <div class="empty-state">
              <el-empty 
                description="创建任务后将在此显示实时执行进度"
                :image-size="140"
              >
                <template #image>
                  <el-icon :size="100" color="#909399">
                    <TrendCharts />
                  </el-icon>
                </template>
                <template #description>
                  <div class="empty-description">
                    <p class="empty-title">暂无执行中的任务</p>
                    <p class="empty-hint">
                      <el-icon><InfoFilled /></el-icon>
                      左侧创建任务后，将在此实时显示：
                    </p>
                    <ul class="feature-list">
                      <li><el-icon><Check /></el-icon> AI思考过程</li>
                      <li><el-icon><Check /></el-icon> 执行动作详情</li>
                      <li><el-icon><Check /></el-icon> 执行结果反馈</li>
                      <li><el-icon><Check /></el-icon> 任务执行轨迹</li>
                    </ul>
                  </div>
                </template>
              </el-empty>
            </div>
          </el-card>
          
          <TaskRealTimePreview 
            v-else
            :task-id="currentTaskId"
          />
        </div>
      </div>
    </div>

    <!-- 快捷指令管理器 -->
    <ShortcutsManager
      v-model="shortcutsManagerVisible"
      @use-shortcut="handleUseShortcut"
    />

    <!-- 提示词卡片管理器 -->
    <PromptCardsManager
      v-model="promptCardsManagerVisible"
      @use-card="handleUseCard"
    />

    <!-- 🆕 计划预览对话框 -->
    <PlanPreviewDialog
      v-model="showPlanPreview"
      :plan="generatedPlan"
      :is-mobile="isMobile"
      @execute="executePlan"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import {
  Cellphone,
  Edit,
  Microphone,
  VideoCamera,
  Loading,
  Setting,
  Promotion,
  List,
  CircleCheck,
  Document,
  Monitor,
  Key,
  Lightning,
  Lock,
  Memo,
  HomeFilled,
  QuestionFilled,
  TrendCharts,
  InfoFilled,
  Check,
  Position,
  VideoPause,
  VideoPlay,
  MagicStick,
  VideoPlay,
  MagicStick,
  View,
  Connection
} from '@element-plus/icons-vue'

import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useDeviceStore } from '@/stores/device'
import { useWebSocketStore } from '@/stores/websocket'
import { speechApi, shortcutApi, planningApi } from '@/api'
import { request } from '@/api/index'
import TopNavigation from '@/components/TopNavigation.vue'
import ShortcutsManager from '@/components/ShortcutsManager.vue'
import PromptCardsManager from '@/components/PromptCardsManager.vue'
import LivePreview from '@/components/LivePreview.vue'
import TaskRealTimePreview from '@/components/TaskRealTimePreview.vue'
import PlanPreviewDialog from '@/components/PlanPreviewDialog.vue'

const router = useRouter()
const taskStore = useTaskStore()
const deviceStore = useDeviceStore()
const wsStore = useWebSocketStore()

// 表单数据
const taskForm = ref({
  instruction: '',
  device_id: null,
  // ✅ 移除所有配置项（由后端环境变量控制）
  // max_steps, speech_platform, speech_api_key 等均由服务端配置
  prompt_card_ids: [],  // 选中的提示词卡片ID列表
  execution_mode: 'step_by_step',  // 执行模式: 'step_by_step' | 'planning'
  preview_plan: true, // 默认开启预览
  max_steps: 100,
  max_history_images: 1,
  // 🆕 模型配置
  ai_provider: 'zhipu',
  ai_base_url: '',
  ai_api_key: '',
  ai_model: '', // 默认留空，使用服务端配置
})

// 🆕 AI厂商预设状态
const aiProviderPreset = ref('default')

// 🆕 处理预设变更
const handlePresetChange = (val) => {
  taskForm.value.ai_provider = val
  switch (val) {
    case 'default':
      taskForm.value.ai_base_url = '' // 空表示使用默认
      taskForm.value.ai_api_key = ''
      taskForm.value.ai_model = '' // 空表示使用默认
      break
    case 'zhipu':
      taskForm.value.ai_base_url = 'https://open.bigmodel.cn/api/paas/v4/'
      taskForm.value.ai_model = 'glm-4-flash'
      break
    case 'openai':
      taskForm.value.ai_base_url = 'https://api.openai.com/v1'
      taskForm.value.ai_model = 'gpt-4o'
      break
    case 'local':
      taskForm.value.ai_base_url = 'http://localhost:8000/v1'
      taskForm.value.ai_model = 'vicuna-7b-v1.5'
      break
    case 'custom':
      // 保持当前值，让用户修改
      break
  }
}

// 🆕 AI模型连接测试
const isTestingConnection = ref(false)

const testModelConnection = async () => {
  isTestingConnection.value = true
  try {
    const response = await request.post('/model/test', {
      provider: taskForm.value.ai_provider,
      base_url: taskForm.value.ai_base_url || null,
      api_key: taskForm.value.ai_api_key || null,
      model_name: taskForm.value.ai_model || null
    })
    
    if (response.success) {
      ElMessage.success(`连接成功! 延迟: ${response.latency_ms}ms, 模型: ${response.model_used}`)
      ElNotification({
        title: '测试成功',
        message: `模型响应: ${response.response}`,
        type: 'success',
        duration: 5000
      })
    } else {
      ElMessage.error(`连接失败: ${response.message}`)
    }
  } catch (error) {
    console.error('Connection test failed:', error)
    ElMessage.error('测试请求失败，请检查网络或配置')
  } finally {
    isTestingConnection.value = false
  }
}

// 当前任务ID(用于实时预览)
const currentTaskId = ref(null)

// 快捷指令相关
const shortcuts = ref([])
const loadingShortcuts = ref(false)
const shortcutsManagerVisible = ref(false)

// 提示词卡片相关
const promptCards = ref([])
const loadingPromptCards = ref(false)
const promptCardsEnabled = ref(false)  // 默认不启用
const promptCardsManagerVisible = ref(false)

// 获取分类图标
const getCategoryIcon = (category) => {
  const iconMap = {
    '社交': '💬',
    '娱乐': '🎮',
    '生活': '🏠',
    '支付': '💰',
    '购物': '🛒',
    '出行': '🚗',
    '工具': '🔧',
    '自定义': '⚡'
  }
  return iconMap[category] || '⚡'
}

// 显示的快捷指令（前8个）
const displayShortcuts = computed(() => {
  // 系统指令优先，然后是自定义指令，取前8个
  return [...shortcuts.value]
    .sort((a, b) => {
      // 系统指令优先
      if (a.is_system && !b.is_system) return -1
      if (!a.is_system && b.is_system) return 1
      // 同类型按ID排序
      return a.id - b.id
    })
    .slice(0, 8)
})

// 显示的提示词卡片（前8个）
const displayPromptCards = computed(() => {
  // 系统卡片优先，然后是自定义卡片，取前8个
  return [...promptCards.value]
    .sort((a, b) => {
      // 系统卡片优先
      if (a.is_system && !b.is_system) return -1
      if (!a.is_system && b.is_system) return 1
      // 同类型按ID排序
      return a.id - b.id
    })
    .slice(0, 8)
})

// 加载快捷指令
async function loadShortcuts() {
  loadingShortcuts.value = true
  try {
    const response = await shortcutApi.list()
    shortcuts.value = response.shortcuts || []
  } catch (error) {
    console.error('Failed to load shortcuts:', error)
  } finally {
    loadingShortcuts.value = false
  }
}

// 使用快捷指令
const useShortcut = (shortcut) => {
  taskForm.value.instruction = shortcut.instruction
  ElMessage.success(`已填入快捷指令：${shortcut.title}`)
}

// 显示快捷指令管理器
const showShortcutsManager = () => {
  shortcutsManagerVisible.value = true
}

// 从管理器使用快捷指令
const handleUseShortcut = (shortcut) => {
  useShortcut(shortcut)
}

// 提示词卡片相关
const selectedPromptCards = computed(() => {
  return promptCards.value.filter(card => taskForm.value.prompt_card_ids.includes(card.id))
})

// 加载提示词卡片
async function loadPromptCards() {
  loadingPromptCards.value = true
  try {
    const response = await request.get('/prompt-cards')
    promptCards.value = response.cards || []
  } catch (error) {
    console.error('Failed to load prompt cards:', error)
  } finally {
    loadingPromptCards.value = false
  }
}

// 移除提示词卡片
const removePromptCard = (cardId) => {
  taskForm.value.prompt_card_ids = taskForm.value.prompt_card_ids.filter(id => id !== cardId)
}

// 切换提示词卡片选择状态
const togglePromptCard = (cardId) => {
  if (taskForm.value.prompt_card_ids.includes(cardId)) {
    removePromptCard(cardId)
  } else {
    taskForm.value.prompt_card_ids.push(cardId)
  }
}

// 显示提示词卡片管理器
const showPromptCardsManager = () => {
  promptCardsManagerVisible.value = true
}

// 从管理器使用提示词卡片
const handleUseCard = (card) => {
  // 如果未启用，先启用
  if (!promptCardsEnabled.value) {
    promptCardsEnabled.value = true
  }
  
  // 如果未选中，则添加
  if (!taskForm.value.prompt_card_ids.includes(card.id)) {
    taskForm.value.prompt_card_ids.push(card.id)
  }
}



// 可用设备
const availableDevices = computed(() => deviceStore.availableDevices)

// 移动端检测
const isMobile = computed(() => window.innerWidth <= 768)

// ✅ 移除所有选项配置（由后端环境变量控制）

// 统计数据
const deviceStats = computed(() => wsStore.deviceStats || {})
const taskStats = computed(() => wsStore.taskStats || {})
const successRate = computed(() => {
  const completed = taskStats.value.completed || 0
  const failed = taskStats.value.failed || 0
  const total = completed + failed
  return total > 0 ? Math.round((completed / total) * 100) : 0
})

// 最近任务
const recentTasks = computed(() => {
  const tasks = taskStore.tasks || []
  return tasks.slice(0, 5)
})

// 语音录制相关
const isRecording = ref(false)
const isTranscribing = ref(false)
const transcriptionProgress = ref('')
const recordingTime = ref(0)
let mediaRecorder = null
let audioChunks = []
let recordingTimer = null

// 开始录音
const startRecording = async () => {
  try {
    // 检查浏览器支持
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      ElMessage.error('您的浏览器不支持录音功能，请使用 Chrome、Edge 或 Firefox 浏览器')
      return
    }

    // 检查是否在安全上下文中（HTTPS 或 localhost）
    const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    if (!isSecureContext) {
      ElMessage.error('录音功能需要在 HTTPS 或 localhost 环境下使用')
      return
    }

    // 请求麦克风权限
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    })
    
    // 检查 MediaRecorder 支持
    if (!window.MediaRecorder) {
      ElMessage.error('您的浏览器不支持 MediaRecorder API')
      stream.getTracks().forEach(track => track.stop())
      return
    }

    // 确定支持的音频格式
    let mimeType = 'audio/webm'
    if (!MediaRecorder.isTypeSupported('audio/webm')) {
      if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4'
      } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
        mimeType = 'audio/ogg'
      } else {
        mimeType = '' // 使用浏览器默认格式
      }
    }

    mediaRecorder = new MediaRecorder(stream, {
      mimeType: mimeType || undefined
    })
    audioChunks = []
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data)
      }
    }
    
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' })
      await transcribeAudio(audioBlob)
      
      // 停止所有音频轨道
      stream.getTracks().forEach(track => track.stop())
    }

    mediaRecorder.onerror = (event) => {
      console.error('MediaRecorder error:', event.error)
      ElMessage.error('录音过程中发生错误：' + (event.error?.message || '未知错误'))
      stopRecording()
    }
    
    mediaRecorder.start()
    isRecording.value = true
    recordingTime.value = 0
    
    // 录音计时器
    recordingTimer = setInterval(() => {
      recordingTime.value++
      if (recordingTime.value >= 60) {
        stopRecording()
        ElMessage.warning('录音时间已达上限（60秒）')
      }
    }, 1000)
    
    ElMessage.success('开始录音...')
  } catch (error) {
    console.error('Failed to start recording:', error)
    
    // 详细的错误提示
    let errorMessage = '无法访问麦克风'
    
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
      errorMessage = '麦克风权限被拒绝，请在浏览器设置中允许访问麦克风'
      ElMessage({
        message: errorMessage,
        type: 'error',
        duration: 5000,
        showClose: true
      })
    } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
      errorMessage = '未检测到麦克风设备，请检查设备连接'
      ElMessage.error(errorMessage)
    } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
      errorMessage = '麦克风被其他应用占用，请关闭其他使用麦克风的应用后重试'
      ElMessage.error(errorMessage)
    } else if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') {
      errorMessage = '麦克风不支持请求的配置'
      ElMessage.error(errorMessage)
    } else {
      errorMessage = `无法访问麦克风：${error.message || '未知错误'}`
      ElMessage({
        message: errorMessage,
        type: 'error',
        duration: 5000,
        showClose: true
      })
    }
  }
}

// 停止录音
const stopRecording = () => {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
    isRecording.value = false
    if (recordingTimer) {
      clearInterval(recordingTimer)
      recordingTimer = null
    }
  }
}

// 切换录音状态
const toggleRecording = () => {
  if (isRecording.value) {
    stopRecording()
  } else {
    startRecording()
  }
}

// 转录音频
const transcribeAudio = async (audioBlob) => {
  isTranscribing.value = true
  transcriptionProgress.value = '正在识别...'
  
  try {
    const result = await speechApi.transcribe(audioBlob, {
      platform: taskForm.value.speech_platform,
      apiKey: taskForm.value.speech_api_key
    })
    
    // 智能追加逻辑：
    // 1. 如果文本框为空，直接设置
    // 2. 如果文本框有内容，在末尾追加（用逗号或句号分隔）
    if (!taskForm.value.instruction || !taskForm.value.instruction.trim()) {
      taskForm.value.instruction = result.text
    } else {
      // 检查最后一个字符，决定分隔符
      const lastChar = taskForm.value.instruction.trim().slice(-1)
      let separator = ''
      
      // 如果最后一个字符不是标点，添加逗号分隔
      if (lastChar && !/[，。、；！？,.\-;!?]/.test(lastChar)) {
        separator = '，'
      }
      
      // 追加新的识别结果
      taskForm.value.instruction = taskForm.value.instruction.trim() + separator + result.text
    }
    
    ElMessage.success(`语音识别完成: ${result.text}`)
  } catch (error) {
    console.error('Transcription failed:', error)
    ElMessage.error('语音识别失败：' + (error.message || '未知错误'))
  } finally {
    isTranscribing.value = false
    transcriptionProgress.value = ''
  }
}

// 提交任务
const isSubmitting = ref(false)
const isCreatingTask = ref(false)

// 🆕 规划模式相关状态
const generatedPlan = ref(null)  // 生成的计划
const showPlanPreview = ref(false)  // 显示计划预览对话框
const isGeneratingPlan = ref(false)  // 正在生成计划

// 新的任务创建方法(用于设备选择行的按钮)
const handleCreateTask = async () => {
  isCreatingTask.value = true
  try {
    // 🆕 根据执行模式调用不同的方法
    if (taskForm.value.execution_mode === 'planning') {
      await handlePlanningMode()
    } else {
      await submitTask()
    }
  } finally {
    isCreatingTask.value = false
  }
}

// 🆕 处理规划模式
const handlePlanningMode = async () => {
  if (!taskForm.value.instruction) {
    ElMessage.warning('请输入任务指令')
    return
  }
  
  // 自动选择设备
  if (!taskForm.value.device_id) {
    const fullyConnectedDevices = deviceStore.devices.filter(d => 
      d.status === 'online' && d.frp_connected && d.ws_connected
    )
    if (fullyConnectedDevices.length > 0) {
      taskForm.value.device_id = fullyConnectedDevices[0].device_id
    } else {
      ElMessage.warning('没有可用设备，请先连接设备')
      return
    }
  }
  
  // 如果需要预览计划
  if (taskForm.value.preview_plan) {
    await generateAndPreviewPlan()
  } else {
    await executeDirectly()
  }
}

// 🆕 生成并预览计划
const generateAndPreviewPlan = async () => {
  isGeneratingPlan.value = true
  try {
    const result = await planningApi.generate({
      instruction: taskForm.value.instruction,
      device_id: taskForm.value.device_id,
      // ✅ 移除 model_config，完全由后端环境变量控制
      prompt_cards: getSelectedPromptCardNames()
    })
    
    generatedPlan.value = result.plan
    showPlanPreview.value = true
    
    ElMessage.success('计划生成成功！请查看并确认')
  } catch (error) {
    console.error('Plan generation failed:', error)
    ElMessage.error('计划生成失败：' + (error.message || '未知错误'))
  } finally {
    isGeneratingPlan.value = false
  }
}

// 🆕 直接执行（不预览）
const executeDirectly = async () => {
  try {
    const result = await planningApi.executeDirect({
      instruction: taskForm.value.instruction,
      device_id: taskForm.value.device_id,
      // ✅ 移除 model_config，完全由后端环境变量控制
      prompt_cards: getSelectedPromptCardNames()
    })
    
    if (result && result.task_id) {
      currentTaskId.value = result.task_id
    }
    
    ElNotification({
      title: '任务创建成功',
      message: '规划模式任务已开始执行',
      type: 'success'
    })
    
    taskForm.value.instruction = ''
  } catch (error) {
    console.error('Task execution failed:', error)
    ElMessage.error('任务执行失败：' + (error.message || '未知错误'))
  }
}

// 🆕 执行已生成的计划
const executePlan = async () => {
  if (!generatedPlan.value) return
  
  // ✅ 验证并自动选择设备（与 submitTask 逻辑一致）
  if (!taskForm.value.device_id) {
    const fullyConnectedDevices = deviceStore.devices.filter(d => 
      d.status === 'online' && d.frp_connected && d.ws_connected
    )
    if (fullyConnectedDevices.length > 0) {
      taskForm.value.device_id = fullyConnectedDevices[0].device_id
      ElMessage.info(`已自动选择设备: ${fullyConnectedDevices[0].device_name || fullyConnectedDevices[0].device_id}`)
    } else {
      const partialDevices = deviceStore.devices.filter(d => 
        d.status === 'online' && d.frp_connected && !d.ws_connected
      )
      if (partialDevices.length > 0) {
        ElMessage.warning('设备FRP已连接但WebSocket未连接，请检查WebSocket配置')
      } else {
        ElMessage.warning('没有可用设备，请先连接设备')
      }
      return
    }
  }
  
  try {
    if (import.meta.env.DEV) {
      console.log('[Plan] Executing with device:', taskForm.value.device_id)
    }
    const result = await planningApi.execute({
      plan: generatedPlan.value,
      device_id: taskForm.value.device_id
    })
    
    if (import.meta.env.DEV) {
      console.log('[Plan] Execution result:', result)
    }
    
    if (result && result.task_id) {
      currentTaskId.value = result.task_id
    }
    
    showPlanPreview.value = false
    generatedPlan.value = null
    
    ElNotification({
      title: '任务开始执行',
      message: '正在按照计划执行任务',
      type: 'success'
    })
    
    taskForm.value.instruction = ''
  } catch (error) {
    console.error('[Plan] Execution failed:', error)
    ElMessage.error('计划执行失败：' + (error.message || '未知错误'))
  }
}

// 🆕 获取选中的提示词卡片名称
const getSelectedPromptCardNames = () => {
  if (!promptCardsEnabled.value || taskForm.value.prompt_card_ids.length === 0) {
    return []
  }
  
  return promptCards.value
    .filter(card => taskForm.value.prompt_card_ids.includes(card.id))
    .map(card => card.name || card.title)
}

// 🆕 模式切换处理
const handleModeChange = (mode) => {
  console.log('执行模式切换:', mode)
  if (mode === 'planning') {
    ElMessage.warning({
      message: '⚠️ 规划模式仍在实验阶段，成功率较低，建议先使用逐步执行模式',
      duration: 5000
    })
  } else {
    ElMessage.success('已切换到逐步执行模式，精确度更高，稳定性好')
  }
}

const submitTask = async () => {
  if (!taskForm.value.instruction) {
    ElMessage.warning('请输入任务指令')
    return
  }
  
  // 如果没有选择设备，自动选择第一个完全连接的设备
  if (!taskForm.value.device_id) {
    const fullyConnectedDevices = deviceStore.devices.filter(d => 
      d.status === 'online' && d.frp_connected && d.ws_connected
    )
    if (fullyConnectedDevices.length > 0) {
      taskForm.value.device_id = fullyConnectedDevices[0].device_id
      ElMessage.info(`已自动选择设备: ${fullyConnectedDevices[0].device_name || fullyConnectedDevices[0].device_id}`)
    } else {
      const partialDevices = deviceStore.devices.filter(d => 
        d.status === 'online' && d.frp_connected && !d.ws_connected
      )
      if (partialDevices.length > 0) {
        ElMessage.warning('设备FRP已连接但WebSocket未连接，请检查WebSocket配置')
      } else {
        ElMessage.warning('没有可用设备，请先连接设备')
      }
      return
    }
  }
  
  isSubmitting.value = true
  
  try {
    const result = await taskStore.createTask(taskForm.value)
    
    // 设置当前任务ID用于实时预览
    if (result && result.task_id) {
      currentTaskId.value = result.task_id
    }
    
    ElNotification({
      title: '任务创建成功',
      message: '任务已开始执行，可在右侧查看实时进度',
      type: 'success'
    })
    
    // 清空表单
    taskForm.value.instruction = ''
  } catch (error) {
    console.error('Failed to create task:', error)
    ElMessage.error('任务创建失败：' + (error.message || '未知错误'))
  } finally {
    isSubmitting.value = false
  }
}

// 辅助函数
const getStatusType = (status) => {
  const typeMap = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return typeMap[status] || 'info'
}

// 设备状态判断函数
const getDeviceStatusType = (device) => {
  if (device.status !== 'online') return 'info'
  if (device.frp_connected && device.ws_connected) return 'success'
  if (device.frp_connected && !device.ws_connected) return 'warning'
  return 'info'
}

const getDeviceStatusText = (device) => {
  if (device.status !== 'online') return '离线'
  if (device.frp_connected && device.ws_connected) return '完全连接'
  if (device.frp_connected && !device.ws_connected) return 'FRP连接'
  return '离线'
}

const getStatusText = (status) => {
  const textMap = {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return textMap[status] || status
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = Math.floor((now - date) / 1000)
  
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
}

// 🆕 计划预览辅助方法
const getComplexityType = (complexity) => {
  const typeMap = {
    simple: 'success',
    medium: 'warning',
    complex: 'danger'
  }
  return typeMap[complexity] || 'info'
}

const getComplexityText = (complexity) => {
  const textMap = {
    simple: '简单任务',
    medium: '中等任务',
    complex: '复杂任务'
  }
  return textMap[complexity] || complexity
}

const getStepIcon = (actionType) => {
  const iconMap = {
    LAUNCH: 'Promotion',
    TAP: 'Pointer',
    TYPE: 'Edit',
    SWIPE: 'DArrowLeft',
    BACK: 'Back',
    HOME: 'HomeFilled',
    WAIT: 'Timer',
    CHECKPOINT: 'Check'
  }
  return iconMap[actionType] || 'Operation'
}

const getActionTypeTag = (actionType) => {
  const tagMap = {
    LAUNCH: 'primary',
    TAP: 'success',
    TYPE: 'warning',
    SWIPE: 'info',
    CHECKPOINT: 'danger'
  }
  return tagMap[actionType] || 'info'
}


// 生命周期
onMounted(async () => {
  await deviceStore.fetchDevices()
  await taskStore.fetchTasks()
  await loadShortcuts()
  await loadPromptCards()
  
  // Auto-resume viewing a running task
  const runningTask = taskStore.tasks.find(t => t.status === 'running')
  if (runningTask) {
    console.log('[Home] Found running task, resuming live view:', runningTask.task_id)
    currentTaskId.value = runningTask.task_id
  }
})

onUnmounted(() => {
  if (recordingTimer) {
    clearInterval(recordingTimer)
  }
})
</script>

<style scoped>
/* 页面布局 */
.home-page {
  min-height: 100vh;
  background: var(--bg-tertiary);
}

/* 主内容区 */
.main-content {
  max-width: 1500px;
  margin: 0 auto;
  padding: 20px 12px;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 380px 380px;
  gap: var(--space-lg);
  align-items: flex-start;
}

/* 三栏布局优化 */
.content-grid.three-column {
  grid-template-columns: 1fr 380px 380px;
}

.middle-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 700px;
}

.right-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 700px;
}

/* 左侧面板 */
.left-panel {
  width: 100%;
}

.task-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-light);
  transition: all 0.3s ease;
}

.task-card:hover {
  box-shadow: var(--shadow-base);
}

.task-card :deep(.el-card__header) {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-lg);
  border-radius: var(--radius-large) var(--radius-large) 0 0;
}

/* 使用统一的 card-header-unified 样式 */

.task-form {
  padding: 8px 0;
}

.task-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.task-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-secondary);
}

/* 语音输入 */
.voice-section {
  text-align: center;
  margin: var(--space-lg) 0;
  padding: var(--space-lg);
  background: var(--bg-tertiary);
  border-radius: var(--radius-large);
  border: 1px solid var(--border-light);
}

.voice-btn {
  height: 48px;
  font-size: 15px;
  padding: 0 32px;
  min-width: 140px;
}

.recording-indicator,
.transcribing-indicator {
  margin-top: var(--space-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  font-size: 14px;
  color: var(--primary-color);
}

.recording-icon {
  font-size: 18px;
  color: var(--error-color);
}

.loading-icon {
  font-size: 18px;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.animate-pulse {
  animation: pulse 1.5s ease-in-out infinite;
}

/* 高级选项 */
.advanced-options {
  margin: 16px 0;
  border: none;
}

.advanced-options :deep(.el-collapse-item__header) {
  background: transparent;
  border: none;
  font-weight: 500;
  color: var(--text-secondary);
}

.advanced-options :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.advanced-options :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

/* 右侧面板 */
.right-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-height: 600px; /* 确保实时预览有足够高度 */
}

/* 任务预览卡片 */
/* 任务预览卡片 - 统一样式 */
.task-preview-card {
  height: 100%;
  min-height: 700px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-light);
  transition: all 0.3s ease;
}

.task-preview-card:hover {
  box-shadow: var(--shadow-base);
}

.task-preview-card :deep(.el-card__body) {
  padding: var(--space-lg);
  flex: 1;
}

.task-preview-card .empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
  padding: var(--space-xl);
}

.empty-description {
  text-align: center;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}

.empty-hint {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-md);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: var(--space-md) 0 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.feature-list li {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  font-size: 14px;
  color: var(--text-tertiary);
}

.feature-list li .el-icon {
  color: var(--success-color);
  font-size: 16px;
}

/* 统一三栏卡片header高度和样式 */
.left-panel .task-card :deep(.el-card__header),
.middle-panel .live-preview-container .preview-header,
.right-panel .task-preview-card :deep(.el-card__header) {
  min-height: 68px;
  height: 68px;
  display: flex;
  align-items: center;
  padding: 16px 20px !important;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-light);
}

/* 确保LivePreview的header也统一 */
.middle-panel :deep(.preview-header) {
  min-height: 68px;
  height: 68px;
  padding: 16px 20px !important;
}

/* card-header统一样式已在design-system.css中定义 */

.stats-card,
.recent-tasks-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
}

.stats-card :deep(.el-card__header),
.recent-tasks-card :deep(.el-card__header) {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-md) var(--space-lg);
}

/* 统计卡片 */
.stat-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.stat-box {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-base);
  transition: all 0.3s ease;
}

.stat-box:hover {
  background: var(--info-bg);
  transform: translateX(4px);
}

.stat-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
  flex-shrink: 0;
}

.stat-icon-wrap.device {
  background: var(--primary-color);
}

.stat-icon-wrap.task {
  background: var(--warning-color);
}

.stat-icon-wrap.success {
  background: var(--success-color);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: var(--space-xs);
}

.stat-label {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* 最近任务 */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item-mini {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-small);
  transition: all 0.3s ease;
  cursor: pointer;
}

.task-item-mini:hover {
  background: var(--info-bg);
  transform: translateX(4px);
}

.task-status {
  flex-shrink: 0;
}

.task-content {
  flex: 1;
  min-width: 0;
}

.task-text {
  font-size: 14px;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: var(--space-xs);
}

.task-time {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 提示词卡片 */
.prompt-cards-section {
  margin: 16px 0 24px 0;
}

.prompt-cards-display {
  margin-top: 12px;
}

.prompt-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr); /* 固定4列，与快捷指令对齐 */
  gap: 12px;
  margin-bottom: 16px;
}

.prompt-card-item {
  padding: var(--space-sm);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  background: var(--bg-primary);
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  min-height: 100px;
  display: flex;
  flex-direction: column;
}

.prompt-card-item:hover {
  border-color: var(--primary-color);
  background: var(--info-bg);
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
}

.prompt-card-item.selected {
  border-color: var(--primary-color);
  background: var(--info-bg);
  box-shadow: var(--shadow-light);
}

.card-header-mini {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.card-title-mini {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  line-height: 1.4;
}

.card-description-mini {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-selection-indicator {
  position: absolute;
  top: 8px;
  right: var(--space-sm);
  color: var(--primary-color);
  font-size: 16px;
}

.selected-cards-summary {
  padding: var(--space-sm) var(--space-sm);
  background: var(--info-bg);
  border-left: 3px solid var(--primary-color);
  border-radius: var(--radius-small);
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

/* 快捷指令 */
.shortcuts-section {
  margin: 16px 0 24px 0;
}

.shortcuts-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr); /* 固定4列，与提示词卡片对齐 */
  gap: 12px;
}

.shortcut-card-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: var(--radius-base);
  background: var(--bg-primary);
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  min-height: 100px;
  display: flex;
  flex-direction: column;
}

.shortcut-card-item:hover {
  border-color: var(--primary-color);
  background: var(--info-bg);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
}

.shortcut-header-mini {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.shortcut-title-mini {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  line-height: 1.4;
}

.shortcut-description-mini {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .shortcuts-grid,
  .prompt-cards-grid {
    grid-template-columns: repeat(2, 1fr); /* 移动端显示2列 */
  }
}

/* 移动端适配 */
@media (max-width: 1280px) {
  .content-grid,
  .content-grid.three-column {
    grid-template-columns: 1fr;
  }
  
  .middle-panel {
    order: -1;
  }
  
  .right-panel {
    order: -2;
  }
  
  .stat-grid {
    flex-direction: row;
    flex-wrap: wrap;
  }
  
  .stat-box {
    flex: 1;
    min-width: 150px;
  }
  
  .shortcuts-grid,
  .prompt-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .main-content {
    padding: 1rem;
  }
  
  .top-nav {
    padding: 0 1rem;
  }
  
  .logo {
    font-size: 1.25rem;
  }
  
  .logo .el-icon {
    font-size: 1.5rem;
  }
  
  .nav-actions .el-button {
    padding: 8px 12px;
    font-size: 14px;
  }
  
  .nav-actions .el-button span {
    display: none;
  }
  
  .stat-grid {
    flex-direction: column;
  }
  
  .stat-box {
    min-width: 100%;
  }
  
  .stat-value {
    font-size: 24px;
  }
  
  .stat-icon-wrap {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }
}

/* 新增的CSS类 - 替代内联样式 */
.device-action-row {
  display: flex;
  gap: var(--space-sm);
  align-items: flex-start;
  width: 100%;
}

.device-selector {
  flex: 1;
  min-width: 0;
}

/* 主页设备选择下拉框专用样式 */
.home-device-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-md);
  padding: var(--space-xs) 0;
}

.home-device-option-left {
  flex: 1;
  min-width: 0;
}

.home-device-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
}

.home-device-option-right {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex-shrink: 0;
}

.create-task-button {
  white-space: nowrap;
  flex-shrink: 0;
}

.voice-input-button {
  flex-shrink: 0;
}

.manage-prompt-button {
  margin-left: var(--space-sm);
}

.prompt-cards-switch {
  margin-bottom: var(--space-sm);
}

.selected-card-tag {
  margin-left: var(--space-xs);
}

.model-option-content {
  display: flex;
  flex-direction: column;
}

.model-description-text {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}

.form-hint-text {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}

.form-hint-text a {
  color: var(--primary-color);
  text-decoration: none;
}

.form-hint-text a:hover {
  text-decoration: underline;
}

.connection-status-text {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}

.connection-status-text.connected {
  color: var(--success-color);
}

.empty-icon {
  color: var(--text-tertiary);
}

.full-width-select,
.full-width-input {
  width: 100%;
}

.recording-indicator,
.transcribing-indicator {
  margin-top: var(--space-sm);
}

/* 执行模式选择样式 */
.mode-description {
  margin-top: var(--space-sm);
}

.mode-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-xs);
  padding: var(--space-sm);
  background: var(--info-bg);
  border-left: 3px solid var(--primary-color);
  border-radius: var(--radius-small);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.mode-hint .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--primary-color);
}

.mode-hint-success {
  background: #f0f9ff;
  border-left-color: var(--success-color);
}

.mode-hint-success .el-icon {
  color: var(--success-color);
}

.mode-hint-warning {
  background: #fffbeb;
  border-left-color: var(--warning-color);
}

.mode-hint-warning .el-icon {
  color: var(--warning-color);
}

.planning-options {
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-base);
  border: 1px dashed var(--border-light);
  margin-bottom: var(--space-md);
}

</style>
