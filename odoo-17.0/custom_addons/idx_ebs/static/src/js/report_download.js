/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.ReportDownload = publicWidget.Widget.extend({
    selector: "#reports_data_table",
    events: {
        "click .o_report_download": "_onDownloadClick",
        "click .o_report_preview": "_onPreviewClick",
    },

    start: function () {
        this._super.apply(this, arguments);
        // 使用委託方式綁定事件到 document
        $(document).on("change", "#check_all_reports", this._onCheckAllChange.bind(this));
        $(document).on("change", ".report-checkbox", this._onCheckboxChange.bind(this));
        return Promise.resolve();
    },

    destroy: function () {
        // 清理事件綁定
        $(document).off("change", "#check_all_reports");
        $(document).off("change", ".report-checkbox");
        this._super.apply(this, arguments);
    },

    /**
     * 顯示 Loading 遮罩
     */
    _showLoading: function () {
        if (this.$loadingOverlay) return;
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
                    <p style="margin-top: 15px; margin-bottom: 0; font-size: 16px; color: #333;">報告下載中，請稍候...</p>
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
    },

    /**
     * 全選/取消全選
     */
    _onCheckAllChange: function (ev) {
        const checked = ev.currentTarget.checked;
        $("#reports_data_table .report-checkbox").prop("checked", checked);
    },

    /**
     * 單個勾選框變更時，更新全選框狀態
     */
    _onCheckboxChange: function () {
        const totalCheckboxes = $("#reports_data_table .report-checkbox").length;
        const checkedCheckboxes = $("#reports_data_table .report-checkbox:checked").length;
        $("#check_all_reports").prop("checked", totalCheckboxes === checkedCheckboxes);
    },

    /**
     * 當點擊瀏覽按鈕時，在新視窗中預覽 PDF 或開啟電子書
     * @param {Event} ev
     */
    _onPreviewClick: function (ev) {
        ev.preventDefault();
        const self = this;
        const reportId = ev.currentTarget.dataset.id;
        const downloadType = ev.currentTarget.dataset.type;

        // 顯示 Loading
        self._showLoading();

        if (downloadType === 'flipbook') {
            this.$loadingOverlay.find('p').text("電子書讀取中，請稍候...");
            jsonrpc("/my/orders/report/get_flipbook_url", {
                report_id: reportId,
            }).then((result) => {
                self._hideLoading();
                if (!result.success) {
                    alert(result.message || "無法獲取電子書連結");
                    return;
                }
                if (result.first_download) {
                    self._updateDownloadDate(reportId);
                }
                if (result.book_url) {
                    window.open(result.book_url, "_blank");
                }
            }).catch((error) => {
                self._hideLoading();
                console.error("FlipHTML5 API Error Details:", error);
                alert("讀取電子書過程中發生錯誤。原因：" + (error.message || "請檢查後端 Log"));
            });
            return;
        }
        // ----------------------------------------------------------------

        jsonrpc("/my/orders/report/download", {
            report_id: reportId,
            download_type: downloadType,
        }).then((result) => {
            // 隱藏 Loading
            self._hideLoading();

            if (!result.success) {
                alert(result.message);
                return;
            }

            if (result.first_download) {
                self._updateDownloadDate(reportId);
            }
            // 將 base64 轉換為 Blob
            const byteCharacters = atob(result.file_content);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: result.content_type });

            // 建立 Blob URL 並在新視窗中開啟
            const blobUrl = URL.createObjectURL(blob);
            const previewWindow = window.open(blobUrl, "_blank");

            // 若瀏覽器阻擋了彈出視窗，提示用戶
            if (!previewWindow || previewWindow.closed || typeof previewWindow.closed === "undefined") {
                alert("瀏覽器阻擋了彈出視窗，請允許此網站的彈出視窗後再試。");
                URL.revokeObjectURL(blobUrl);
                return;
            }

            // 當視窗關閉時釋放 Blob URL
            const checkClosed = setInterval(() => {
                if (previewWindow.closed) {
                    clearInterval(checkClosed);
                    URL.revokeObjectURL(blobUrl);

                }
            }, 1000);
        }).catch((error) => {
            // 隱藏 Loading
            self._hideLoading();
            alert("預覽過程中發生錯誤，請稍後再試。");
        });
    },

    /**
     */
    _updateDownloadDate: function (reportId) {
        const now = new Date();
        const formattedDate = `${now.getFullYear()}年${String(now.getMonth() + 1).padStart(2, '0')}月${String(now.getDate()).padStart(2, '0')}日`;
        this.$el.find(`tr[data-id="${reportId}"] span[name="download_date"]`).text(formattedDate);
    },

    /**
     * 當點擊下載按鈕時，發送 API 記錄下載類型
     * @param {Event} ev
     */
    _onDownloadClick: function (ev) {
        ev.preventDefault();
        const self = this;
        const reportId = ev.currentTarget.dataset.id;
        const downloadType = ev.currentTarget.dataset.type;

        // 顯示 Loading
        self._showLoading();

        jsonrpc("/my/orders/report/download", {
            report_id: reportId,
            download_type: downloadType,
        }).then((result) => {
            // 隱藏 Loading
            self._hideLoading();

            if (!result.success) {
                alert(result.message);
                return;
            }

            if (result.first_download) {
                self._updateDownloadDate(reportId);
            }
            // 將 base64 轉換為 Blob 並下載
            const byteCharacters = atob(result.file_content);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: result.content_type });

            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = result.file_name;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href);
        }).catch((error) => {
            // 隱藏 Loading
            self._hideLoading();
            alert("下載過程中發生錯誤，請稍後再試。");
        });
    },
});

/**
 * 批次下載報告按鈕 Widget
 */
publicWidget.registry.BatchReportDownload = publicWidget.Widget.extend({
    selector: "#btn_batch_report_download",
    events: {
        "click": "_onBatchDownloadClick",
    },

    /**
     * 批次下載按鈕點擊事件
     */
    _onBatchDownloadClick: function (ev) {
        ev.preventDefault();
        const self = this;

        // 取得所有勾選的報告
        const checkedCheckboxes = $("#reports_data_table .report-checkbox:checked");
        
        if (checkedCheckboxes.length === 0) {
            alert("請選取要下載的報告書");
            return;
        }

        // 取得權限資訊
        const hasPdf = this.$el.data("has-pdf");
        const hasExcel = this.$el.data("has-excel");

        // 取得訂單 ID
        const orderId = $("#reports_data_table").data("order-id");

        // 收集選中報告的資訊
        const reportInfos = [];
        checkedCheckboxes.each(function() {
            const $row = $(this).closest("tr");
            const reportInfo = {
                id: parseInt($row.data("id")),
                upload_date: $row.data("upload-date"),
                year: $row.data("year"),
                month: $row.data("month"),
                report_name: $row.data("report-name"),
                inspect_number: $row.data("inspect-number"),
            };
            reportInfos.push(reportInfo);
        });

        // 發送批次下載請求
        jsonrpc("/my/orders/report/batch_download", {
            report_infos: reportInfos,
            download_pdf: hasPdf,
            download_excel: hasExcel,
            order_id: orderId,
        }).then((result) => {
            if (!result.success) {
                alert(result.message || "批次下載失敗，請稍後再試。");
                return;
            }

            // 記錄待處理的任務 ID 到 localStorage（作為輪詢 fallback）
            if (result.task_id) {
                const pendingTasks = JSON.parse(localStorage.getItem('pending_batch_tasks') || '[]');
                if (!pendingTasks.includes(result.task_id)) {
                    pendingTasks.push(result.task_id);
                    localStorage.setItem('pending_batch_tasks', JSON.stringify(pendingTasks));
                }
            }

            alert("批次下載任務已啟動\n任務將在背景執行\n完成後系統會自動通知您");

        }).catch((error) => {
            console.error("批次下載錯誤:", error);
            alert("批次下載過程中發生錯誤，請稍後再試。");
        });
    },
});

export default {
    ReportDownload: publicWidget.registry.ReportDownload,
    BatchReportDownload: publicWidget.registry.BatchReportDownload,
};

