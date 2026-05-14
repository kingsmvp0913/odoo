/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// 根據 URL 參數切換 body class
function toggleCartMode() {
    
    const urlParams = new URLSearchParams(window.location.search);
    const hasGeneral = urlParams.get('general');
    
    if (hasGeneral) {
        document.body.classList.add('cart-general-mode');
    } else {
        document.body.classList.remove('cart-general-mode');
    }
    
    // 更新空購物車提示
    updateEmptyCartMessage(hasGeneral);
}

// 更新空購物車訊息
function updateEmptyCartMessage(hasGeneral) {
    // 移除所有現有的空購物車訊息
    document.querySelectorAll('.js_cart_lines.alert-info').forEach(el => el.remove());
    
    // 計算可見產品數量
    setTimeout(() => {
        const cartContainer = document.querySelector('#cart_products');
        if (!cartContainer) return;
        
        const cartProducts = cartContainer.querySelectorAll('.o_cart_product');
        let visibleCount = 0;
        
        cartProducts.forEach(line => {
            const styles = window.getComputedStyle(line);
            if (styles.display !== 'none') {
                visibleCount++;
            }
        });
        
        if (visibleCount === 0) {
            const message = document.createElement('div');
            message.className = 'js_cart_lines alert alert-info';
            message.textContent = hasGeneral ? '您的產品購物車是空的' : '您的檢測項目購物車是空的';
            cartContainer.parentNode.insertBefore(message, cartContainer);
        }
    }, 100);
}

// 使用 Odoo 原生 publicWidget 註冊方式
publicWidget.registry.cartFilter = publicWidget.Widget.extend({
    selector: '.oe_website_sale',
    
    start: function () {
        this._super.apply(this, arguments);
        
        // 頁面載入時切換模式
        toggleCartMode();
        
        // 監聽瀏覽器前進/後退
        window.addEventListener('popstate', toggleCartMode);
    },
});

// 覆寫原生 WebsiteSale 的 _changeCartQuantity 方法
publicWidget.registry.WebsiteSale.include({
    /**
     * AJAX 更新後無需做任何事，CSS 會自動處理
     */
    _changeCartQuantity: function ($input, value, $dom_optional, line_id, productIDs) {
        // 調用原生方法
        this._super.apply(this, arguments);
        
        // 延遲更新空購物車訊息
        setTimeout(() => {
            const urlParams = new URLSearchParams(window.location.search);
            const hasGeneral = urlParams.get('general');
            updateEmptyCartMessage(hasGeneral);
        }, 500);
    },
});

export default {
    WebsiteSale: publicWidget.registry.WebsiteSale,
    cartFilter: publicWidget.registry.cartFilter,
};
