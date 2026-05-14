/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

// ============================================
// 全域物流查詢通知機制
// ============================================
(function () {
    'use strict';

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCarrierNotification);
    } else {
        initCarrierNotification();
    }

    function initCarrierNotification() {
        checkRecentCompletedCarrierTasks();
        startCarrierPolling();
    }

    /**
     * 檢查最近完成的物流查詢任務
     */
    function checkRecentCompletedCarrierTasks() {
        const completedTasksStr = localStorage.getItem('completed_carrier_tasks');
        if (completedTasksStr) {
            try {
                const completedTasks = JSON.parse(completedTasksStr);
                completedTasks.forEach(taskData => {
                    showCarrierCompletionNotification(taskData);
                });
                localStorage.removeItem('completed_carrier_tasks');
            } catch (e) {
                console.error("解析完成的物流查詢任務失敗:", e);
            }
        }
    }

    /**
     * 啟動物流查詢輪詢
     */
    function startCarrierPolling() {
        checkPendingCarrierTasks();
        setInterval(checkPendingCarrierTasks, 3000);
    }

    /**
     * 檢查待處理的物流查詢任務
     */
    function checkPendingCarrierTasks() {
        const pendingTasks = JSON.parse(localStorage.getItem('pending_carrier_tasks') || '[]');
        if (pendingTasks.length === 0) return;

        pendingTasks.forEach(task => {
            jsonrpc("/my/orders/report/get_carrier_status", {
                uuid: task.uuid,
                report_id: task.report_id,
            }).then((result) => {
                if (result.success && result.message) {
                    // 查詢完成
                    removePendingCarrierTask(task.uuid);

                    const taskData = {
                        uuid: task.uuid,
                        report_id: task.report_id,
                        order_id: task.order_id,
                        message: result.message,
                        reload: result.reload,
                    };

                    showCarrierCompletionNotification(taskData);
                } else if (result.error) {
                    // 查詢失敗
                    removePendingCarrierTask(task.uuid);
                    showCarrierNotification(
                        '✗ 物流查詢失敗',
                        result.error_message || '查詢過程中發生錯誤',
                        'error'
                    );
                }
            }).catch((error) => {
                console.error("輪詢物流狀態時發生錯誤:", error);
            });
        });
    }

    /**
     * 從待處理列表中移除任務
     */
    function removePendingCarrierTask(uuid) {
        const pendingTasks = JSON.parse(localStorage.getItem('pending_carrier_tasks') || '[]');
        const updatedTasks = pendingTasks.filter(t => t.uuid !== uuid);
        localStorage.setItem('pending_carrier_tasks', JSON.stringify(updatedTasks));
    }

    /**
     * 顯示物流查詢完成通知
     */
    function showCarrierCompletionNotification(taskData) {
        showCarrierNotification(
            '✓ 物流狀態查詢完成',
            taskData.message || '物流狀態已更新',
            'success',
            taskData.reload && taskData.order_id ? taskData.order_id : null
        );
    }

    /**
     * 顯示物流查詢通知
     */
    function showCarrierNotification(title, message, type, orderId = null) {
        const notification = document.createElement('div');
        notification.className = `carrier-notification ${type === 'success' ? 'bg-primary' : 'bg-danger'}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            color: white;
            padding: 20px 30px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 100000;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        `;

        const isOnOrderPage = orderId && window.location.pathname.includes(`/my/orders/${orderId}`);
        const viewOrderButton = orderId ? `
            <div style="margin-top: 12px;">
                <a href="${isOnOrderPage ? 'javascript:window.location.reload()' : `/my/orders/${orderId}`}" 
                   style="color: white; background: rgba(255,255,255,0.2); 
                          padding: 6px 12px; border-radius: 4px; text-decoration: none; 
                          display: inline-block; font-weight: bold;">
                    ${isOnOrderPage ? '重新載入頁面' : '立即前往訂單'}
                </a>
            </div>
        ` : '';

        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 15px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0; font-size: 18px; font-weight: bold;">${title}</h4>
                    <p style="margin: 0; font-size: 14px; opacity: 0.95;">${message}</p>
                    ${viewOrderButton}
                </div>
                <button class="btn-close-notification" style="background: none; border: none; color: white; 
                               font-size: 24px; cursor: pointer; padding: 0; line-height: 1; 
                               opacity: 0.8; margin-left: 10px;">
                    ×
                </button>
            </div>
        `;

        if (!document.getElementById('carrier-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'carrier-notification-styles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        const closeBtn = notification.querySelector('.btn-close-notification');
        closeBtn.addEventListener('click', () => notification.remove());

        document.body.appendChild(notification);

        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIF2m98OScTgwOUKzn77llHQU7k9nyxnkpBSh+zO/glkILElyx6OyrWBUIQ5zd8sFuJAUuhM/z1YU1Bxdqv/DkmU0MDk+s5++2ZBwGOJHX8sR1JQUme8Pw2pBACxJcsOjuq1kVCEGb3PKxbB8FLoTP89mJNQgXar/w4pxMDA9Rr+fx');
            audio.volume = 0.3;
            audio.play().catch(() => { });
        } catch (e) { }

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(400px)';
            notification.style.transition = 'all 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 12000);
    }

    // 將函數暴露到全域供 Widget 使用
    window.CarrierNotificationHelper = {
        addPendingTask: function (task) {
            const pendingTasks = JSON.parse(localStorage.getItem('pending_carrier_tasks') || '[]');
            pendingTasks.push(task);
            localStorage.setItem('pending_carrier_tasks', JSON.stringify(pendingTasks));
        },
        showNotification: showCarrierNotification
    };
})();

// ============================================
// Widget: 物流資料儲存與查詢
// ============================================
publicWidget.registry.CarrierSave = publicWidget.Widget.extend({
    selector: "#reports_data_block",
    events: {
        "click #btn_save_carrier_reports": "_onSaveClick",
        "change .carrier-select": "_onCarrierChange",
        "input .carrier-number-input": "_onCarrierNumberChange",
        "click .btn-fetch-carrier-type": "_onFetchCarrierTypeClick",
    },

    /**
     * 初始化時記錄所有欄位的初始值
     */
    start: function () {
        this._super.apply(this, arguments);
        this._recordInitialValues();
    },

    /**
     * 記錄所有 carrier 和 carrier_number 的初始值
     */
    _recordInitialValues: function () {
        const $rows = $("#carrier_reports_table tbody tr");
        $rows.each((index, row) => {
            const $row = $(row);
            const $carrierSelect = $row.find('.carrier-select');
            const $carrierNumberInput = $row.find('.carrier-number-input');
            const $carrierTypeSpan = $row.find('.carrier-type-display');

            // 記錄初始值
            $carrierSelect.data('initial-value', $carrierSelect.val() || "");
            $carrierNumberInput.data('initial-value', $carrierNumberInput.val() || "");
            $carrierTypeSpan.data('initial-value', $carrierTypeSpan.text().trim() || "");
        });
    },

    /**
     * 顯示 Loading 遮罩
     */
    _showLoading: function () {
        if (this.$loadingOverlay) return;
        
        // 禁用所有查詢按鈕和儲存按鈕
        $("#btn_save_carrier_reports").prop('disabled', true);
        $(".btn-fetch-carrier-type").prop('disabled', true);
        
        this.$loadingOverlay = $(`
            <div class="o_loading_overlay" style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
            ">
                <div style="
                    background: white;
                    padding: 30px 50px;
                    border-radius: 10px;
                    text-align: center;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                ">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p style="margin-top: 15px; margin-bottom: 0; font-size: 16px; color: #333;">處理中，請稍候...</p>
                </div>
            </div>
        `);
        $("body").append(this.$loadingOverlay);
    },

    /**
     * 隱藏 Loading 遮罩
     */
    _hideLoading: function () {
        if (this.$loadingOverlay) {
            this.$loadingOverlay.remove();
            this.$loadingOverlay = null;
        }
        
        // 恢復儲存按鈕
        $("#btn_save_carrier_reports").prop('disabled', false);
        
        // 恢復查詢按鈕（依據是否有變更決定是否啟用）
        const $rows = $("#carrier_reports_table tbody tr");
        $rows.each((index, row) => {
            const $row = $(row);
            const $carrierSelect = $row.find('.carrier-select');
            const $carrierNumberInput = $row.find('.carrier-number-input');
            const $fetchButton = $row.find('.btn-fetch-carrier-type');
            
            const carrierOldValue = $carrierSelect.data('initial-value') || "";
            const carrierNewValue = $carrierSelect.val() || "";
            const carrierNumberOldValue = $carrierNumberInput.data('initial-value') || "";
            const carrierNumberNewValue = $carrierNumberInput.val() || "";
            
            const isUnchanged = carrierOldValue === carrierNewValue && carrierNumberOldValue === carrierNumberNewValue;
            $fetchButton.prop('disabled', !isUnchanged);
        });
    },

    /**
     * 顯示成功訊息
     */
    _showSuccessMessage: function (message) {
        const notification = document.createElement('div');
        notification.className = 'carrier-notification bg-primary';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            color: white;
            padding: 20px 30px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        `;

        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 15px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0; font-size: 18px; font-weight: bold;">✓ 操作成功</h4>
                    <p style="margin: 0; font-size: 14px; opacity: 0.95;">${message}</p>
                </div>
                <button class="btn-close-notification" style="background: none; border: none; color: white; 
                               font-size: 24px; cursor: pointer; padding: 0; line-height: 1; 
                               opacity: 0.8; margin-left: 10px;">
                    ×
                </button>
            </div>
        `;

        if (!document.getElementById('carrier-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'carrier-notification-styles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        const closeBtn = notification.querySelector('.btn-close-notification');
        closeBtn.addEventListener('click', () => notification.remove());

        document.body.appendChild(notification);

        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIF2m98OScTgwOUKzn77llHQU7k9nyxnkpBSh+zO/glkILElyx6OyrWBUIQ5zd8sFuJAUuhM/z1YU1Bxdqv/DkmU0MDk+s5++2ZBwGOJHX8sR1JQUme8Pw2pBACxJcsOjuq1kVCEGb3PKxbB8FLoTP89mJNQgXar/w4pxMDA9Rr+fx');
            audio.volume = 0.3;
            audio.play().catch(() => {});
        } catch (e) {}

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(400px)';
            notification.style.transition = 'all 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 8000);
    },

    /**
     * 顯示錯誤訊息
     */
    _showErrorMessage: function (message) {
        const notification = document.createElement('div');
        notification.className = 'carrier-notification bg-danger';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            color: white;
            padding: 20px 30px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        `;

        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 15px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0; font-size: 18px; font-weight: bold;">✗ 操作失敗</h4>
                    <p style="margin: 0; font-size: 14px; opacity: 0.95;">${message}</p>
                </div>
                <button class="btn-close-notification" style="background: none; border: none; color: white; 
                               font-size: 24px; cursor: pointer; padding: 0; line-height: 1; 
                               opacity: 0.8; margin-left: 10px;">
                    ×
                </button>
            </div>
        `;

        if (!document.getElementById('carrier-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'carrier-notification-styles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        const closeBtn = notification.querySelector('.btn-close-notification');
        closeBtn.addEventListener('click', () => notification.remove());

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(400px)';
            notification.style.transition = 'all 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 8000);
    },

    /**
     * 收集所有 report 的資料
     */
    _collectReportData: function () {
        const reportData = [];
        const $rows = $("#carrier_reports_table tbody tr");

        $rows.each((index, row) => {
            const $row = $(row);
            const $mailInput = $row.find('.carrier-mail-input');
            const $carrierSelect = $row.find('.carrier-select');
            const $resvInput = $row.find('.carrier-resv-input');
            const $carrierNumberInput = $row.find('.carrier-number-input');
            const $intlCarrierSelect = $row.find('.intl-carrier-select');
            const $intlCarrierNumberInput = $row.find('.intl-carrier-number-input');

            const reportId = $carrierSelect.data("report-id");
            const mail = $mailInput.val() || "";
            const carrierValue = $carrierSelect.val() || "";
            const resvNumber = $resvInput.val() || "";
            const carrierNumber = $carrierNumberInput.val() || "";
            const intlCarrier = $intlCarrierSelect.val() || "";
            const intlCarrierNumber = $intlCarrierNumberInput.val() || "";

            // 轉換物流選擇為資料庫值
            let carrier = false;
            if (carrierValue === "黑貓") {
                carrier = "tcat";
            } else if (carrierValue === "中華郵政") {
                carrier = "post";
            }

            reportData.push({
                report_id: reportId,
                mail: mail,
                carrier: carrier,
                resv_number: resvNumber,
                carrier_number: carrierNumber,
                intl_carrier: intlCarrier,
                intl_carrier_number: intlCarrierNumber,
            });
        });

        return reportData;
    },

    /**
     * 檢查並更新物流類型顯示及查詢按鈕狀態
     */
    _updateCarrierTypeDisplay: function ($row) {
        const $carrierSelect = $row.find(".carrier-select");
        const $carrierNumberInput = $row.find(".carrier-number-input");
        const $carrierTypeSpan = $row.find(".carrier-type-display");
        const $fetchButton = $row.find(".btn-fetch-carrier-type");

        const carrierOldValue = $carrierSelect.data('initial-value') || "";
        const carrierNewValue = $carrierSelect.val() || "";
        const carrierNumberOldValue = $carrierNumberInput.data('initial-value') || "";
        const carrierNumberNewValue = $carrierNumberInput.val() || "";
        const oldCarrierType = $carrierTypeSpan.data('initial-value') || "";

        const isUnchanged = carrierOldValue === carrierNewValue && carrierNumberOldValue === carrierNumberNewValue;

        // 更新物流類型顯示
        $carrierTypeSpan.text(isUnchanged ? oldCarrierType : "");

        // 更新查詢按鈕狀態：有變更時禁用
        $fetchButton.prop('disabled', !isUnchanged);
    },

    /**
     * 當選擇國內物流時，更新物流類型顯示
     */
    _onCarrierChange: function (ev) {
        this._updateCarrierTypeDisplay($(ev.currentTarget).closest("tr"));
    },

    /**
     * 當輸入物流編號時，更新物流類型顯示
     */
    _onCarrierNumberChange: function (ev) {
        this._updateCarrierTypeDisplay($(ev.currentTarget).closest("tr"));
    },

    /**
     * 當點擊儲存按鈕時，收集所有資料並送出
     */
    _onSaveClick: function (ev) {
        ev.preventDefault();
        const self = this;
        const reportData = self._collectReportData();

        if (reportData.length === 0) {
            self._showErrorMessage("沒有可儲存的資料");
            return;
        }

        // 顯示 Loading
        self._showLoading();

        jsonrpc("/my/orders/report/save_carrier", {
            report_data: reportData,
        }).then((result) => {
            // 隱藏 Loading
            self._hideLoading();

            if (result.success) {
                self._showSuccessMessage(result.message || "儲存成功");
                // 儲存成功後，更新 initial-value
                self._updateInitialValuesAfterSave();
            } else {
                self._showErrorMessage(result.message || "儲存失敗");
            }
        }).catch((error) => {
            // 隱藏 Loading
            self._hideLoading();
            console.error("儲存過程中發生錯誤:", error);
            self._showErrorMessage("儲存過程中發生錯誤，請稍後再試。");
        });
    },

    /**
     * 儲存成功後更新所有欄位的初始值
     */
    _updateInitialValuesAfterSave: function () {
        const $rows = $("#carrier_reports_table tbody tr");
        $rows.each((index, row) => {
            const $row = $(row);
            const $carrierSelect = $row.find('.carrier-select');
            const $carrierNumberInput = $row.find('.carrier-number-input');
            const $carrierTypeSpan = $row.find('.carrier-type-display');
            const $fetchButton = $row.find(".btn-fetch-carrier-type");

            // 更新為當前值
            $carrierSelect.data('initial-value', $carrierSelect.val() || "");
            $carrierNumberInput.data('initial-value', $carrierNumberInput.val() || "");
            $carrierTypeSpan.data('initial-value', $carrierTypeSpan.text().trim() || "");
            $fetchButton.prop('disabled', false);
        });
    },

    /**
     * 點擊查詢物流狀態按鈕
     */
    _onFetchCarrierTypeClick: function (ev) {
        ev.preventDefault();
        const self = this;
        const $button = $(ev.currentTarget);
        const orderId = $button.data('order-id');
        const reportId = $button.data('report-id');
        const $row = $button.closest('tr');
        const carrier = $row.find('.carrier-select').val() || "";
        const carrierNumber = $row.find('.carrier-number-input').val() || "";
        const uuid = Math.random().toString(36).substring(2, 15);

        if (!carrier || !carrierNumber) {
            alert("請確認物流及物流編號是否已填寫完整");
            return;
        }

        self._showLoading();

        jsonrpc("/my/orders/report/fetch_carrier_type", {
            uuid: uuid,
            report_id: reportId,
            carrier: carrier,
            carrier_number: carrierNumber,
        }).then((result) => {
            self._hideLoading();
            if (result.success) {
                if (result.from_cache) {
                    // 從快取取得，直接顯示
                    const $carrierTypeSpan = $row.find('.carrier-type-display');
                    $carrierTypeSpan.text(result.carrier_type || "");
                    $carrierTypeSpan.data('initial-value', result.carrier_type || "");
                    self._showSuccessMessage(result.message || "已成功取得物流狀態。");
                } else {
                    // 異步查詢，加入全域輪詢列表
                    window.CarrierNotificationHelper.addPendingTask({
                        uuid: uuid,
                        report_id: reportId,
                        order_id: orderId,
                    });
                    self._showSuccessMessage(result.message || "已送出查詢請求，請稍候…");
                }
            } else {
                self._showErrorMessage(result.message || "查詢請求失敗");
            }
        }).catch((error) => {
            self._hideLoading();
            console.error("查詢過程中發生錯誤:", error);
            self._showErrorMessage("查詢過程中發生錯誤，請稍後再試。");
        });
    },
});
