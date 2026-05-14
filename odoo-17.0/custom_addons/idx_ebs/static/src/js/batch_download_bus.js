/** @odoo-module **/

import { jsonrpc } from "@web/core/network/rpc_service";


// 直接執行，不依賴 Widget
(function () {
    'use strict';

    // 等待 DOM 載入完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBatchNotification);
    } else {
        initBatchNotification();
    }

    function initBatchNotification() {

        // 檢查最近完成的任務
        checkRecentCompletedTasks();

        // 啟動輪詢
        startPolling();
    }

    /**
     * 檢查最近完成的任務
     */
    function checkRecentCompletedTasks() {

        const completedTasksStr = localStorage.getItem('completed_batch_tasks');

        if (completedTasksStr) {
            try {
                const completedTasks = JSON.parse(completedTasksStr);
                completedTasks.forEach(taskData => {
                    showCompletionNotification(taskData);
                });
                localStorage.removeItem('completed_batch_tasks');
            } catch (e) {
                console.error("解析完成任務資料失敗:", e);
            }
        }
    }

    /**
     * 啟動輪詢
     */
    function startPolling() {
        // 立即檢查一次
        checkPendingTasks();

        // 每 3 秒檢查一次
        setInterval(checkPendingTasks, 3000);
    }

    /**
     * 檢查待處理的任務
     */
    function checkPendingTasks() {
        const pendingTasks = JSON.parse(localStorage.getItem('pending_batch_tasks') || '[]');

        if (pendingTasks.length === 0) {
            return;
        }


        pendingTasks.forEach(taskId => {

            jsonrpc(`/my/orders/report/batch_download/status/${taskId}`, {})
                .then(function (result) {

                    if (result.success && (result.state === 'done' || result.state === 'failed')) {

                        // 從待處理列表中移除
                        const updatedTasks = pendingTasks.filter(id => id !== taskId);
                        localStorage.setItem('pending_batch_tasks', JSON.stringify(updatedTasks));

                        // 顯示通知
                        const taskData = {
                            task_id: taskId,
                            status: result.state,
                            error_message: result.error_message,
                            order_id: result.order_id,
                            order_name: result.order_name,
                        };

                        showCompletionNotification(taskData);

                        // 如果在訂單頁面，重新載入
                        if (window.location.pathname.includes('/my/orders/')) {
                            setTimeout(function () {
                                window.location.reload();
                            }, 2000);
                        }
                    }
                })
                .catch(function (error) {
                    console.error("檢查任務狀態失敗:", error);
                });
        });
    }

    /**
     * 顯示完成通知
     */
    function showCompletionNotification(taskData) {

        if (taskData.status === 'done') {
            const orderText = taskData.order_name ? `訂單 ${taskData.order_name}` : '批次下載';
            showNotification(
                '✓ 批次下載完成！',
                `${orderText} 的報告已準備好`,
                'success',
                taskData.task_id
            );
        } else if (taskData.status === 'failed') {
            showNotification(
                '✗ 批次下載失敗',
                taskData.error_message || '處理過程中發生錯誤',
                'error',
                taskData.task_id
            );
        }
    }

    /**
     * 顯示通知
     */
    function showNotification(title, message, type, taskId) {
        const notification = document.createElement('div');
        notification.className = `batch-download-notification ${type === 'success' ? 'bg-primary' : 'bg-danger'}`;
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

        const downloadLink = type === 'success' && taskId ? `
            <div style="margin-top: 12px;">
                <a href="/my/orders/report/batch_download/download/${taskId}" 
                   style="color: white; background: rgba(255,255,255,0.2); 
                          padding: 6px 12px; border-radius: 4px; text-decoration: none; 
                          display: inline-block; font-weight: bold;"
                   download>
                    立即下載
                </a>
            </div>
        ` : '';

        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 15px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0; font-size: 18px; font-weight: bold;">${title}</h4>
                    <p style="margin: 0; font-size: 14px; opacity: 0.95;">${message}</p>
                    ${downloadLink}
                </div>
                <button class="btn-close-notification" style="background: none; border: none; color: white; 
                               font-size: 24px; cursor: pointer; padding: 0; line-height: 1; 
                               opacity: 0.8; margin-left: 10px;">
                    ×
                </button>
            </div>
        `;

        // 添加動畫樣式
        if (!document.getElementById('batch-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'batch-notification-styles';
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

        // 綁定關閉按鈕
        const closeBtn = notification.querySelector('.btn-close-notification');
        closeBtn.addEventListener('click', function () {
            notification.remove();
        });

        document.body.appendChild(notification);

        // 播放提示音
        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIF2m98OScTgwOUKzn77llHQU7k9nyxnkpBSh+zO/glkILElyx6OyrWBUIQ5zd8sFuJAUuhM/z1YU1Bxdqv/DkmU0MDk+s5++2ZBwGOJHX8sR1JQUme8Pw2pBACxJcsOjuq1kVCEGb3PKxbB8FLoTP89mJNQgXar/w4pxMDA9Rr+fx');
            audio.volume = 0.3;
            audio.play().catch(() => { });
        } catch (e) {
            // 忽略音效錯誤
        }

        // 12 秒後自動移除
        setTimeout(function () {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(400px)';
            notification.style.transition = 'all 0.3s ease-out';
            setTimeout(function () {
                notification.remove();
            }, 300);
        }, 12000);
    }

})();
