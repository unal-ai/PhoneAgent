<template>
  <div class="top-nav-unified">
    <div class="nav-content-unified">
      <div class="logo-unified" @click="router.push('/')" style="cursor: pointer;">
        <el-icon><Cellphone /></el-icon>
        <span>PhoneAgent</span>
        <span class="powered-by">Powered by</span>
        <svg class="unal-logo" fill='none' viewBox='0 0 120 46' height='20' width='52' xmlns='http://www.w3.org/2000/svg'>
          <g clip-path='url(#clip0_29_2)'>
            <path d='M38.899 19.2528H20.7827L18.8653 38.3573H9.06149C7.47403 38.4724 6.8393 37.67 7.15729 35.9503L8.92952 19.3635H4.59322L4.43108 20.2865H2.04047L2.20261 19.3635H1.85193L0.0231471 37.468C-0.268453 43.2052 2.19506 46.0232 7.4137 45.9218H25.464L26.6687 33.8378L27.3776 26.8342H37.2361C38.8361 26.7204 39.4771 27.5227 39.1591 29.2413L37.3699 45.9031H44.4739L46.3027 27.7253C46.5993 21.9632 44.1314 19.139 38.899 19.2528ZM7.47591 21.7499H8.15841L8.03775 22.4291H7.36468L7.47591 21.7499ZM3.94466 23.9581H3.26406L3.38283 23.2789H4.06533L3.94466 23.9581ZM5.11358 22.1983H3.53555L3.81458 20.628H5.39261L5.11358 22.1983ZM6.54267 23.2789H5.52835L5.71689 22.2696H6.7312L6.54267 23.2789Z' fill='#2A2F88'></path>
            <path d='M84.9373 36.0215L86.8095 19.234H78.7326L77.0358 35.9315C76.3395 42.3015 78.8992 45.6323 84.7149 45.9237H91.6245L92.1318 38.695L87.3939 38.6744C85.731 38.5118 84.9122 37.6275 84.9373 36.0215Z' fill='#2A2F88'></path>
            <path d='M68.0087 19.3297L58.9798 19.311C53.227 19.5511 49.932 22.3878 49.0949 27.821L47.2831 45.8862H54.636L55.441 37.7945L67.2885 37.8508L66.4703 45.9181H73.5554L75.3842 27.7591C75.6997 22.4935 73.2412 19.6837 68.0087 19.3297ZM68.218 28.9974L67.971 31.2149H56.1423L56.4459 28.3895C56.422 26.5697 57.3647 25.6347 59.2739 25.5847L66.4382 25.5659C68.0068 25.8061 68.6001 26.9499 68.218 28.9974Z' fill='#2A2F88'></path>
            <path d='M108.121 15.0934C107.163 10.8161 104.77 6.99093 101.335 4.24758C97.9009 1.50424 93.6303 0.00618293 89.2264 0H89.0002C80.0617 0.105063 72.3752 6.36568 70.3221 15.0371C68.7018 15.4343 67.1558 16.0867 65.7426 16.9695H68.169C71.572 17.2003 74.1229 18.3541 75.7368 20.3278C76.512 19.5118 77.0179 18.4794 77.1866 17.3691C78.2292 11.5156 83.2367 7.21557 89.0812 7.14615H89.2434C92.0609 7.15277 94.7889 8.13156 96.9624 9.91568C99.1358 11.6998 100.62 14.1788 101.163 16.9301C101.951 20.9488 105.122 21.7124 106.308 21.9957C110.337 22.9675 112.948 26.4571 112.805 30.6783C112.674 34.5375 109.731 37.8714 105.806 38.6068C105.22 38.7156 103.581 38.6687 100.925 38.6612L100.548 45.8974C101.937 45.8974 105.9 46.1282 107.135 45.8974C114.343 44.5466 119.746 38.1003 119.99 30.9204C120.254 23.2752 115.487 16.9189 108.121 15.0934Z' fill='#2A2F88'></path>
            <path d='M92.9556 45.9162H99.2149L99.741 38.695H93.4326L92.9556 45.9162Z' fill='#2A2F88'></path>
            <path d='M6.48047 18.4498H8.66747L9.05208 16.2735H6.86508L6.48047 18.4498Z' fill='#2A2F88'></path>
            <path d='M4.15962 17.7725H2.7984L2.55896 19.1271H3.92018L4.15962 17.7725Z' fill='#2A2F88'></path>
            <path d='M4.86471 14.8363H3.66752L3.45636 16.0277H4.65355L4.86471 14.8363Z' fill='#2A2F88'></path>
            <path d='M7.40245 11.9434H6.49937L6.341 12.8402H7.24408L7.40245 11.9434Z' fill='#2A2F88'></path>
            <path d='M8.54115 14.6375L8.74288 13.5025H7.60413L7.4024 14.6375H8.54115Z' fill='#2A2F88'></path>
          </g>
          <defs>
            <clipPath id='clip0_29_2'>
              <rect width='120' height='46' fill='white'></rect>
            </clipPath>
          </defs>
        </svg>
      </div>
      <div class="nav-actions-unified">
        <!-- 核心导航（始终显示）-->
        <el-button 
          @click="router.push('/')" 
          text 
          :type="currentRoute === '/' ? 'primary' : ''"
          class="nav-btn-unified"
        >
          <el-icon><HomeFilled /></el-icon>
          首页
        </el-button>
        
        <el-button 
          @click="router.push('/tasks')" 
          text
          :type="currentRoute === '/tasks' ? 'primary' : ''"
          class="nav-btn-unified"
        >
          <el-icon><Document /></el-icon>
          任务
        </el-button>
        
        <el-button 
          @click="router.push('/devices')" 
          text
          :type="currentRoute === '/devices' ? 'primary' : ''"
          class="nav-btn-unified"
        >
          <el-icon><Monitor /></el-icon>
          设备
        </el-button>

        <el-divider direction="vertical" class="nav-divider-unified" />
        
        <!-- 配置菜单（下拉）-->
        <el-dropdown trigger="hover" @command="handleCommand">
          <el-button text class="nav-dropdown-btn">
            <el-icon><Setting /></el-icon>
            <span class="nav-text">配置</span>
            <el-icon class="dropdown-icon" :size="12"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="/app-config">
                <el-icon><Iphone /></el-icon>
                <span>应用配置</span>
              </el-dropdown-item>
              <el-dropdown-item command="/anti-detection">
                <el-icon><Lock /></el-icon>
                <span>防风控配置</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        
        <!-- 工具菜单（下拉）-->
        <el-dropdown trigger="hover" @command="handleCommand">
          <el-button text class="nav-dropdown-btn">
            <el-icon><Tools /></el-icon>
            <span class="nav-text">工具</span>
            <el-icon class="dropdown-icon" :size="12"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="/logs">
                <el-icon><Document /></el-icon>
                <span>系统日志</span>
              </el-dropdown-item>
              <el-dropdown-item command="/diagnostic">
                <el-icon><DataAnalysis /></el-icon>
                <span>性能诊断</span>
              </el-dropdown-item>
              <el-dropdown-item command="/model-stats">
                <el-icon><Coin /></el-icon>
                <span>模型统计</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-divider direction="vertical" class="nav-divider-unified" />
        
        <!-- GitHub -->
        <el-tooltip content="GitHub 仓库" placement="bottom">
          <el-button
            @click="openGitHub"
            text
            circle
            class="nav-btn-circle-unified"
          >
            <svg class="github-icon" viewBox="0 0 16 16" width="18" height="18" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
          </el-button>
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Cellphone,
  HomeFilled,
  Document,
  Monitor,
  Setting,
  Lock,
  DataAnalysis,
  ArrowDown,
  Tools,
  Iphone,
  Coin  // ✅ 新增: 模型统计图标
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

const currentRoute = computed(() => route.path)

// 处理下拉菜单命令
const handleCommand = (command) => {
  router.push(command)
}

// GitHub 跳转
const openGitHub = () => {
  window.open('https://github.com/unal-ai/PhoneAgent', '_blank')
}
</script>

<style scoped>
/* 统一导航栏样式 */
.top-nav-unified {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-light);
  position: sticky;
  top: 0;
  z-index: 1000;
  box-shadow: var(--shadow-light);
  backdrop-filter: blur(10px);
}

.nav-content-unified {
  max-width: 1400px;
  margin: 0 auto;
  height: 64px;
  padding: 0 var(--space-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-unified {
  display: flex;
  align-items: end;
  gap: var(--space-sm);
  font-size: 20px;
  font-weight: 600;
  color: var(--primary-color);
  transition: all 0.3s ease;
}

.logo-unified:hover {
  color: var(--primary-light);
}

.logo-unified .el-icon {
  font-size: 24px;
}

.logo-unified .powered-by {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: 8px;
  opacity: 0.7;
}

.logo-unified .unal-logo {
  margin-left: 2px;
  opacity: 0.9;
}

.nav-actions-unified {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.nav-divider-unified {
  height: 20px;
  margin: 0 var(--space-xs);
}

/* 普通导航按钮 */
.nav-btn-unified {
  font-size: 15px;
  color: var(--text-secondary);
  padding: 10px var(--space-md);
  border-radius: var(--radius-base);
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
}

.nav-btn-unified .el-icon {
  font-size: 16px;
}

.nav-btn-unified:hover {
  color: var(--primary-color);
  background: var(--info-bg);
}

.nav-btn-unified.el-button--primary {
  color: var(--primary-color);
  background: var(--info-bg);
  font-weight: 500;
}

/* 下拉导航按钮 */
.nav-dropdown-btn {
  font-size: 15px;
  color: var(--text-secondary);
  padding: 10px var(--space-md);
  border-radius: var(--radius-base);
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 40px;
}

.nav-dropdown-btn .el-icon {
  font-size: 16px;
}

.nav-dropdown-btn .dropdown-icon {
  margin-left: 2px;
  transition: transform 0.3s ease;
}

.nav-dropdown-btn:hover {
  color: var(--primary-color);
  background: var(--info-bg);
}

.nav-dropdown-btn:hover .dropdown-icon {
  transform: rotate(180deg);
}

.nav-btn-circle-unified {
  padding: 10px;
  width: 40px;
  height: 40px;
  color: var(--text-secondary);
  transition: all 0.3s ease;
}

.nav-btn-circle-unified:hover {
  color: var(--primary-color);
  background: var(--info-bg);
}

.github-icon {
  display: block;
}

/* 下拉菜单样式优化 */
.el-dropdown-menu {
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-dark);
  border: 1px solid var(--border-light);
  padding: var(--space-xs) 0;
}

.el-dropdown-menu__item {
  padding: 10px var(--space-md);
  font-size: 14px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  transition: all 0.3s ease;
}

.el-dropdown-menu__item:hover {
  background: var(--info-bg);
  color: var(--primary-color);
}

.el-dropdown-menu__item .el-icon {
  font-size: 16px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .nav-content-unified {
    padding: 0 var(--space-md);
  }
  
  .logo-unified {
    font-size: 18px;
  }
  
  .logo-unified .el-icon {
    font-size: 20px;
  }
  
  .nav-btn-unified,
  .nav-dropdown-btn {
    padding: 8px var(--space-sm);
    font-size: 14px;
  }
  
  /* 移动端隐藏文字，只显示图标 */
  .nav-text {
    display: none;
  }
  
  .nav-btn-circle-unified {
    width: 36px;
    height: 36px;
    padding: 8px;
  }
  
  .nav-divider-unified {
    margin: 0 2px;
  }
}
</style>
