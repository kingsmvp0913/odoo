/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DeleteCartBtn = publicWidget.Widget.extend({
    selector: '.js_delete_cart',
    events: {
        'click': '_onClickDelete',
    },

    _onClickDelete: async function (ev) {
        ev.preventDefault();

        const cartProducts = document.querySelectorAll('.detects_widget_container[data-category]');
        const categories = new Set();
        cartProducts.forEach(el => {
            const cat = el.dataset.category;
            if (cat) categories.add(cat);
        });

        if (categories.size === 0) {
            alert('購物車中沒有送檢報告可刪除');
            return;
        }

        const orderId = this.el.dataset.orderId;
        if (!orderId) return;

        if (!confirm('確定要刪除所有送檢報告嗎？')) return;

        try {
            const response = await fetch(`/shop/reports/delete?order_id=${orderId}`, {
                method: 'DELETE',
            });
            const result = await response.json();

            if (result.success) {
                window.location.reload();
            } else {
                alert(`刪除失敗：${result.error}`);
            }
        } catch (error) {
            alert(`刪除失敗：${error.message}`);
        }
    },
});

publicWidget.registry.BatchUploadBtn = publicWidget.Widget.extend({
    selector: '.js_batch_upload',
    events: {
        'click': '_onClickUpload',
    },

    _onClickUpload: function (ev) {
        ev.preventDefault();

        const cartProducts = document.querySelectorAll('.detects_widget_container[data-category]');
        const categories = new Set();
        cartProducts.forEach(el => {
            const cat = el.dataset.category;
            if (cat) categories.add(cat);
        });

        // if (categories.size === 0) {
        //     alert('購物車中沒有送檢報告可刪除');
        //     return;
        // }

        const orderId = this.el.dataset.orderId;
        // if (!orderId) {
        //     alert('無法取得訂單ID');
        //     return;
        // }

        // 建立隱藏的 file input
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.xlsx';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // 前端先驗證副檔名
            if (!file.name.toLowerCase().endsWith('.xlsx')) {
                alert('檔案格式錯誤，僅支援 .xlsx 格式');
                return;
            }

            // 建立 FormData 並上傳
            const formData = new FormData();
            formData.append('file', file);
            if (orderId) {
                formData.append('order_id', orderId);
            }

            try {
                const response = await fetch('/shop/report/upload', {
                    method: 'POST',
                    body: formData,
                });
                const result = await response.json();

                if (result.success) {
                    alert(result.message || '檔案批次上傳成功');
                    window.location.reload();
                } else {
                    alert(`上傳失敗：${result.error}`);
                }
            } catch (error) {
                alert(`上傳失敗：${error.message}`);
            }
        });

        document.body.appendChild(fileInput);
        fileInput.click();
        document.body.removeChild(fileInput);
    },
});

publicWidget.registry.DownloadHumanTemplateBtn = publicWidget.Widget.extend({
    selector: '.js_download_human_template',
    events: {
        'click': '_onClickDownloadHumanTemplate',
    },

    _onClickDownloadHumanTemplate: function (ev) {
        ev.preventDefault();
        window.location.href = '/shop/report/download_template?category=0';
    },
});

publicWidget.registry.DownloadAnimalTemplateBtn = publicWidget.Widget.extend({
    selector: '.js_download_animal_template',
    events: {
        'click': '_onClickDownloadAnimalTemplate',
    },

    _onClickDownloadAnimalTemplate: function (ev) {
        ev.preventDefault();
        window.location.href = '/shop/report/download_template?category=1';
    },
});

export default publicWidget.registry.DeleteCartBtn;
