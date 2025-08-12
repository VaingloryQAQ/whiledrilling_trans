/**
 * 前端性能优化模块
 * 包含虚拟滚动、懒加载、防抖、缓存等功能
 */

class PerformanceOptimizer {
    constructor() {
        this.intersectionObserver = null;
        this.resizeObserver = null;
        this.debounceTimers = new Map();
        this.cache = new Map();
        this.init();
    }

    init() {
        this.setupIntersectionObserver();
        this.setupResizeObserver();
        this.setupGlobalEventListeners();
    }

    /**
     * 设置交叉观察器用于懒加载
     */
    setupIntersectionObserver() {
        this.intersectionObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        this.loadImage(img);
                        this.intersectionObserver.unobserve(img);
                    }
                });
            },
            {
                rootMargin: '50px', // 提前50px开始加载
                threshold: 0.1
            }
        );
    }

    /**
     * 设置尺寸观察器用于响应式处理
     */
    setupResizeObserver() {
        this.resizeObserver = new ResizeObserver(
            this.debounce(() => {
                this.handleResize();
            }, 100)
        );
    }

    /**
     * 设置全局事件监听器
     */
    setupGlobalEventListeners() {
        // 优化滚动事件
        let ticking = false;
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    this.handleScroll();
                    ticking = false;
                });
                ticking = true;
            }
        });

        // 优化窗口大小变化
        window.addEventListener('resize', this.debounce(() => {
            this.handleResize();
        }, 150));
    }

    /**
     * 防抖函数
     */
    debounce(func, delay) {
        return (...args) => {
            const key = func.toString();
            clearTimeout(this.debounceTimers.get(key));
            this.debounceTimers.set(key, setTimeout(() => func.apply(this, args), delay));
        };
    }

    /**
     * 节流函数
     */
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * 懒加载图片
     */
    setupLazyLoading() {
        const images = document.querySelectorAll('img[data-src]');
        images.forEach(img => {
            this.intersectionObserver.observe(img);
        });
    }

    /**
     * 加载图片
     */
    loadImage(img) {
        const src = img.dataset.src;
        if (!src) return;

        // 检查缓存
        if (this.cache.has(src)) {
            img.src = this.cache.get(src);
            return;
        }

        // 创建新图片对象进行预加载
        const tempImg = new Image();
        tempImg.onload = () => {
            img.src = src;
            this.cache.set(src, src);
            img.classList.add('loaded');
        };
        tempImg.onerror = () => {
            img.classList.add('error');
            console.warn(`Failed to load image: ${src}`);
        };
        tempImg.src = src;
    }

    /**
     * 虚拟滚动实现
     */
    setupVirtualScroll(container, items, itemHeight, renderItem) {
        const visibleCount = Math.ceil(container.clientHeight / itemHeight);
        const totalHeight = items.length * itemHeight;
        
        // 创建滚动容器
        const scrollContainer = document.createElement('div');
        scrollContainer.style.height = `${totalHeight}px`;
        scrollContainer.style.position = 'relative';
        
        // 创建可见内容容器
        const visibleContainer = document.createElement('div');
        visibleContainer.style.position = 'absolute';
        visibleContainer.style.top = '0';
        visibleContainer.style.left = '0';
        visibleContainer.style.right = '0';
        
        scrollContainer.appendChild(visibleContainer);
        container.appendChild(scrollContainer);

        let startIndex = 0;
        let endIndex = visibleCount;

        const updateVisibleItems = () => {
            const scrollTop = container.scrollTop;
            startIndex = Math.floor(scrollTop / itemHeight);
            endIndex = Math.min(startIndex + visibleCount + 1, items.length);

            // 更新可见容器的位置
            visibleContainer.style.transform = `translateY(${startIndex * itemHeight}px)`;

            // 清空并重新渲染可见项
            visibleContainer.innerHTML = '';
            for (let i = startIndex; i < endIndex; i++) {
                const itemElement = renderItem(items[i], i);
                visibleContainer.appendChild(itemElement);
            }
        };

        container.addEventListener('scroll', this.throttle(updateVisibleItems, 16));
        updateVisibleItems();
    }

    /**
     * 处理滚动事件
     */
    handleScroll() {
        // 可以在这里添加滚动相关的优化逻辑
        // 比如：隐藏/显示固定元素、更新进度条等
    }

    /**
     * 处理窗口大小变化
     */
    handleResize() {
        // 重新计算布局
        this.updateLayout();
    }

    /**
     * 更新布局
     */
    updateLayout() {
        // 根据窗口大小调整网格布局
        const container = document.querySelector('.image-grid');
        if (container) {
            const width = window.innerWidth;
            let columns = 4; // 默认4列

            if (width < 768) columns = 2;
            else if (width < 1024) columns = 3;
            else if (width < 1440) columns = 4;
            else columns = 5;

            container.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
        }
    }

    /**
     * 优化DOM操作
     */
    batchDOMUpdates(updates) {
        // 使用DocumentFragment批量更新DOM
        const fragment = document.createDocumentFragment();
        
        updates.forEach(update => {
            const element = update();
            if (element) {
                fragment.appendChild(element);
            }
        });

        return fragment;
    }

    /**
     * 内存管理
     */
    cleanup() {
        // 清理观察器
        if (this.intersectionObserver) {
            this.intersectionObserver.disconnect();
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }

        // 清理定时器
        this.debounceTimers.forEach(timer => clearTimeout(timer));
        this.debounceTimers.clear();

        // 清理缓存
        this.cache.clear();
    }
}

/**
 * 图片网格优化器
 */
class ImageGridOptimizer {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            itemHeight: 200,
            columns: 4,
            gap: 10,
            ...options
        };
        this.images = [];
        this.visibleImages = new Set();
        this.optimizer = new PerformanceOptimizer();
        this.init();
    }

    init() {
        this.setupGrid();
        this.setupLazyLoading();
    }

    setupGrid() {
        this.container.style.display = 'grid';
        this.container.style.gridTemplateColumns = `repeat(${this.options.columns}, 1fr)`;
        this.container.style.gap = `${this.options.gap}px`;
        this.container.style.padding = `${this.options.gap}px`;
    }

    setupLazyLoading() {
        // 为所有图片设置懒加载
        const images = this.container.querySelectorAll('img');
        images.forEach(img => {
            if (!img.src) {
                img.dataset.src = img.src;
                img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkxvYWRpbmcuLi48L3RleHQ+PC9zdmc+';
                this.optimizer.intersectionObserver.observe(img);
            }
        });
    }

    addImages(newImages) {
        this.images.push(...newImages);
        this.renderImages(newImages);
    }

    renderImages(images) {
        const fragment = this.optimizer.batchDOMUpdates(
            images.map(image => () => this.createImageElement(image))
        );
        this.container.appendChild(fragment);
    }

    createImageElement(image) {
        const div = document.createElement('div');
        div.className = 'image-item';
        div.style.height = `${this.options.itemHeight}px`;
        div.style.overflow = 'hidden';
        div.style.borderRadius = '8px';
        div.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';

        const img = document.createElement('img');
        img.dataset.src = image.url;
        img.alt = image.name || '';
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        img.style.transition = 'transform 0.3s ease';

        // 添加悬停效果
        div.addEventListener('mouseenter', () => {
            img.style.transform = 'scale(1.05)';
        });
        div.addEventListener('mouseleave', () => {
            img.style.transform = 'scale(1)';
        });

        div.appendChild(img);
        return div;
    }

    updateLayout() {
        const width = window.innerWidth;
        let columns = 4;

        if (width < 768) columns = 2;
        else if (width < 1024) columns = 3;
        else if (width < 1440) columns = 4;
        else columns = 5;

        this.options.columns = columns;
        this.container.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
    }

    cleanup() {
        this.optimizer.cleanup();
    }
}

/**
 * 搜索优化器
 */
class SearchOptimizer {
    constructor(inputElement, callback, options = {}) {
        this.input = inputElement;
        this.callback = callback;
        this.options = {
            delay: 300,
            minLength: 2,
            ...options
        };
        this.optimizer = new PerformanceOptimizer();
        this.setupSearch();
    }

    setupSearch() {
        this.input.addEventListener('input', this.optimizer.debounce((e) => {
            const query = e.target.value.trim();
            if (query.length >= this.options.minLength) {
                this.callback(query);
            }
        }, this.options.delay));
    }
}

// 全局性能优化器实例
window.performanceOptimizer = new PerformanceOptimizer();

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    window.performanceOptimizer.cleanup();
});

// 导出类供其他模块使用
window.ImageGridOptimizer = ImageGridOptimizer;
window.SearchOptimizer = SearchOptimizer;