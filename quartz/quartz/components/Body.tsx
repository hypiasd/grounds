import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { componentRegistry } from "./registry"

const Body: QuartzComponent = ({ children }: QuartzComponentProps) => {
  return <div id="quartz-body">{children}</div>
}

// 左侧栏隐藏 toggle：注入到 .page-header（center 区域始终存在）
// 用 inline script 而不是 Preact island，避免 Body 整个变成 client component
// 持久化到 localStorage（key: grounds:sidebar-hidden），符合用户硬约束
//
// 关键：必须监听 SPA `nav` 事件。micromorph 在 SPA 导航时按标签名匹配 .page-header
// 的子节点，旧页面的 <button class="sidebar-toggle"> 与新页面的 <header> 不匹配，
// 按钮会被移除。postscript.js 以 spaPreserve 不重新执行，所以 IIFE 只跑一次——
// 必须靠 nav 事件监听重新注入。参考 popover.inline.ts 的 setupPopovers + nav 范式。
Body.afterDOMLoaded = `
(function () {
  if (window.matchMedia('(max-width: 768px)').matches) return;

  var STORAGE_KEY = 'grounds:sidebar-hidden';

  function applyState(btn, leftSidebar, hidden) {
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

  function injectToggle() {
    if (window.matchMedia('(max-width: 768px)').matches) return;
    var leftSidebar = document.querySelector('.left.sidebar');
    var pageHeader = document.querySelector('.center > .page-header');
    if (!leftSidebar || !pageHeader) return;
    if (pageHeader.querySelector('.sidebar-toggle')) return;

    var btn = document.createElement('button');
    btn.className = 'sidebar-toggle';
    btn.type = 'button';
    btn.setAttribute('aria-label', '隐藏/显示左侧栏');
    btn.setAttribute('aria-expanded', 'true');
    btn.textContent = '◀';

    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'true') applyState(btn, leftSidebar, true);
    } catch (e) {}

    btn.addEventListener('click', function () {
      var hidden = leftSidebar.classList.contains('hidden');
      var next = !hidden;
      applyState(btn, leftSidebar, next);
      try { localStorage.setItem(STORAGE_KEY, String(next)); } catch (e) {}
    });

    pageHeader.insertBefore(btn, pageHeader.firstChild);
  }

  injectToggle();
  document.addEventListener('nav', injectToggle);
})();
`

// 自注册到 componentRegistry，让 componentResources.ts 能收集 Body.afterDOMLoaded。
// 注册一个工厂（而不是 Body 本身），因为 getAllComponents() 会把函数视为构造器并调用它——
// 直接注册 Body 会导致 Body(undefined) 返回 JSX 而非组件实例。工厂返回 Body 单例即可。
const BodyFactory: QuartzComponentConstructor = () => Body
componentRegistry.register("Body", BodyFactory, "internal")

export default (() => Body) satisfies QuartzComponentConstructor
