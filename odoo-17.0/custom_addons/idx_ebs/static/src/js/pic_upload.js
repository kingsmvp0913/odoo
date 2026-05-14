/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.PicUpload = publicWidget.Widget.extend({
    selector: "#reports_data_table",
    events: {
        "click .o_pic_upload": "_onUploadClick",
    },

    /**
     * 當前選中的報告 ID
     */
    currentReportId: null,

    /**
     * 初始化
     */
    start: function () {
        this._super.apply(this, arguments);
        this._setupModalEvents();
    },

    /**
     * 設置 Modal 事件
     */
    _setupModalEvents: function () {
        const self = this;
        const modal = document.getElementById("modalPicUpload");
        const fileInput = document.getElementById("picFileInput");
        const previewContainer = document.getElementById("picPreviewContainer");
        const previewImg = document.getElementById("picPreview");
        const uploadBtn = document.getElementById("btnUploadPic");

        if (!modal || !fileInput || !uploadBtn) {
            return;
        }

        // 檢查是否已經綁定過事件，防止重複綁定
        if (uploadBtn.dataset.bindedUpload === "true") {
            return;
        }
        uploadBtn.dataset.bindedUpload = "true";

        // 當 Modal 關閉時重置
        modal.addEventListener("hidden.bs.modal", function () {
            fileInput.value = "";
            previewContainer.classList.add("d-none");
            previewImg.src = "";
            self.currentReportId = null;
        });

        // 檔案選擇預覽
        fileInput.addEventListener("change", function (ev) {
            const file = ev.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    previewImg.src = e.target.result;
                    previewContainer.classList.remove("d-none");
                };
                reader.readAsDataURL(file);
            } else {
                previewContainer.classList.add("d-none");
                previewImg.src = "";
            }
        });

        // 上傳按鈕點擊
        uploadBtn.addEventListener("click", function () {
            self._handleUpload();
        });
    },

    /**
     * 當點擊上傳按鈕時，記錄報告 ID
     * @param {Event} ev
     */
    _onUploadClick: function (ev) {
        ev.preventDefault();
        this.currentReportId = ev.currentTarget.dataset.reportId;
    },

    /**
     * 將圖片壓縮至指定大小上限（預設 800KB）
     * @param {File} file
     * @returns {Promise<string>} base64 字串（不含前綴）
     */
    _compressImage: function (file) {
        return new Promise(function (resolve) {
            const reader = new FileReader();
            reader.onload = function (e) {
                const img = new Image();
                img.onload = function () {
                    const MAX_SIZE = 800 * 1024; // 800KB 目標
                    const canvas = document.createElement("canvas");

                    // 若原圖超過 1920px 寬，等比縮小
                    let width = img.width;
                    let height = img.height;
                    if (width > 1920) {
                        height = Math.round((height * 1920) / width);
                        width = 1920;
                    }
                    canvas.width = width;
                    canvas.height = height;
                    canvas.getContext("2d").drawImage(img, 0, 0, width, height);

                    // 逐步降低品質直到低於目標大小
                    let quality = 0.85;
                    let base64Data;
                    do {
                        const dataUrl = canvas.toDataURL("image/jpeg", quality);
                        base64Data = dataUrl.split(",")[1];
                        quality -= 0.1;
                    } while (base64Data.length > MAX_SIZE && quality > 0.2);

                    console.log("[PicUpload] 壓縮後大小:", {
                        base64_kb: (base64Data.length / 1024).toFixed(1) + " KB",
                        quality: quality.toFixed(1),
                    });
                    resolve(base64Data);
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    },

    /**
     * 處理上傳邏輯
     */
    _handleUpload: function () {
        const self = this;
        const fileInput = document.getElementById("picFileInput");
        const file = fileInput.files[0];

        if (!file) {
            alert("請選擇一張照片");
            return;
        }

        if (!this.currentReportId) {
            alert("無法取得報告 ID，請重新操作");
            return;
        }

        // 印出原始檔案資訊
        console.log("[PicUpload] 原始檔案:", {
            name: file.name,
            type: file.type,
            size_bytes: file.size,
            size_kb: (file.size / 1024).toFixed(1) + " KB",
        });

        // 壓縮後送出
        self._compressImage(file).then(function (base64Data) {
            // 發送 API
            jsonrpc("/my/orders/report/upload_pic", {
                report_id: self.currentReportId,
                file_data: base64Data,
                file_name: file.name.replace(/\.[^.]+$/, ".jpg"), // 壓縮後統一為 jpg
            }).then(function (result) {
                console.log("[PicUpload] 回應:", result);
                if (result.success) {
                    alert(result.message);
                    try {
                        const modal = bootstrap.Modal.getInstance(document.getElementById("modalPicUpload"));
                        if (modal) {
                            modal.hide();
                        }
                    } catch (e) {
                        console.error("關閉 Modal 錯誤:", e);
                    }
                    location.reload();
                } else {
                    alert(result.message);
                }
            }).catch(function (error) {
                console.error("[PicUpload] 上傳錯誤 status:", error?.status);
                console.error("[PicUpload] 上傳錯誤 detail:", error);
                alert("上傳失敗，請稍後再試");
            });
        });
    },
});

export default publicWidget.registry.PicUpload;
