import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { componentRegistry } from "./registry"

const Body: QuartzComponent = ({ children }: QuartzComponentProps) => {
  return <div id="quartz-body">{children}</div>
}

// 左侧栏隐藏 toggle：注入到 .page-header（center 区域始终存在）
// 用 inline script 而不是 Preact island，避免 Body 整个变成 client component
// 持久化到 localStorage（key: grounds:sidebar-hidden），符合用户硬约束
Body.afterDOMLoaded = `
(function () {
  // 仅桌面端启用（移动端用 hamburger 菜单）
  if (window.matchMedia('(max-width: 768px)').matches) return;

  var STORAGE_KEY = 'grounds:sidebar-hidden';
  var leftSidebar = document.querySelector('.left.sidebar');
  var pageHeader = document.querySelector('.center > .page-header');
  if (!leftSidebar || !pageHeader) return;

  // 防止重复注入（SPA 导航后 postscript 重新执行）
  if (pageHeader.querySelector('.sidebar-toggle')) return;

  var btn = document.createElement('button');
  btn.className = 'sidebar-toggle';
  btn.type = 'button';
  btn.setAttribute('aria-label', '隐藏/显示左侧栏');
  btn.setAttribute('aria-expanded', 'true');
  btn.textContent = '◀';

  function applyState(hidden) {
    if (hidden) {
      leftSidebar.classList.add('hidden');
      btn.textContent = '▶';
      btn.setAttribute('aria-expanded', 'false');
    } else {
      leftSidebar.classList.remove('hidden');
      btn.textContent = '◀';
      btn.setAttribute('aria-expanded', 'true');
    }
  }

  // 从 localStorage 恢复状态
  try {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'true') applyState(true);
  } catch (e) {
    // localStorage 不可用时静默失败（隐私模式等）
  }

  btn.addEventListener('click', function () {
    var hidden = leftSidebar.classList.contains('hidden');
    var next = !hidden;
    applyState(next);
    try { localStorage.setItem(STORAGE_KEY, String(next)); } catch (e) {}
  });

  // 插入到 page-header 最前面
  pageHeader.insertBefore(btn, pageHeader.firstChild);
})();
`

// 自注册到 componentRegistry，让 componentResources.ts 能收集 Body.afterDOMLoaded。
// 注册一个工厂（而不是 Body 本身），因为 getAllComponents() 会把函数视为构造器并调用它——
// 直接注册 Body 会导致 Body(undefined) 返回 JSX 而非组件实例。工厂返回 Body 单例即可。
const BodyFactory: QuartzComponentConstructor = () => Body
componentRegistry.register("Body", BodyFactory, "internal")

export default (() => Body) satisfies QuartzComponentConstructor
