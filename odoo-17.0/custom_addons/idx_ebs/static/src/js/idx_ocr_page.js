/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/* =========================================================
 * Base Component
 * =======================================================*/
class IdxOcrBase extends Component {
    setup() {
        this.notification = useService("notification");

        this.state = useState({
            files: [],
            submitUrl: "",
            page: "",
            isProcessing: false,
            isCameraOn: false,
        });

        this.videoStream = null;

        onWillUnmount(() => {
            this._stopCameraStream();
        });
    }

    /* ================= 上傳檔案 ================= */
    openFileDialog() {
        if (this.state.isProcessing) return;

        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.multiple = true;

        input.onchange = (e) => {
            Array.from(e.target.files).forEach((f) => {
                this.state.files.push(f);
            });
            e.target.value = "";
        };

        input.click();
    }

    /* ================= 刪除檔案 ================= */
    removeFile(file) {
        if (this.state.isProcessing) return;

        const idx = this.state.files.indexOf(file);
        if (idx !== -1) {
            this.state.files.splice(idx, 1);
        }
    }

    async _waitForElement(id, timeout = 2000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.getElementById(id);
            if (el) return el;
            await new Promise((r) => setTimeout(r, 30));
        }
        throw new Error(`等待 #${id} 超時，DOM 未渲染`);
    }

    /* ================= 開啟相機 ================= */
    async startCamera() {
        if (this.state.isCameraOn || this.state.isProcessing) return;

        this.state.isCameraOn = true;
        await new Promise((resolve) => setTimeout(resolve, 0));

        try {
            const video = await this._waitForElement("ocr_camera_preview");
            if (!video) {
                throw new Error("Video element not rendered");
            }

            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" },
                audio: false,
            });

            video.srcObject = stream;
            await video.play();

            this.videoStream = stream;

        } catch (err) {
            console.error(err);
            this.notification.add(
                "相機畫面初始化失敗，請確認瀏覽器權限",
                { type: "danger" }
            );
            this.state.isCameraOn = false;
        }
    }

    /* ================= 拍照 ================= */
    capturePhoto() {
        const video = document.getElementById("ocr_camera_preview");
        if (!video) return;

        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0);

        canvas.toBlob((blob) => {
            if (!blob) return;

            const file = new File(
                [blob],
                `凌越送檢單_${Date.now()}.jpg`,
                { type: "image/jpeg" }
            );

            this.state.files.push(file);
        }, "image/jpeg");
    }

    /* ================= 關閉相機 ================= */
    stopCamera() {
        this._stopCameraStream();
        this.state.isCameraOn = false;
    }

    _stopCameraStream() {
        if (this.videoStream) {
            this.videoStream.getTracks().forEach((t) => t.stop());
            this.videoStream = null;
        }

        const video = document.getElementById("ocr_camera_preview");
        if (video) {
            video.srcObject = null;
        }
    }

    async _logFrontendError(message) {
        try {
            await fetch("/idx_ocr/error_log", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                }),
            });
        } catch (logError) {
            console.error("Failed to write OCR frontend error to server log.", logError);
        }
    }

    /* ================= 開始辨識 ================= */
    async startRecognize() {
        if (!this.state.files.length) {
            this.notification.add("請先上傳圖片", { type: "warning" });
            return;
        }
        if (this.state.isProcessing) return;

        if (this.state.isCameraOn) {
            this.stopCamera();
        }

        this.state.isProcessing = true;

        try {
            const formData = new FormData();
            formData.append("page", this.state.page);

            this.state.files.forEach((file) => {
                formData.append("files", file);
            });

            const res = await fetch(this.state.submitUrl, {
                method: "POST",
                body: formData,
            });

            const result = await res.json();

            if (result.success) {
                this.notification.add(
                    `${result.message}`,
                    { type: "success", sticky: true }
                );

                if (result.errors && result.errors.length) {
                    result.errors.forEach((err) => {
                        this.notification.add(
                            `${err.file}：${err.error}`,
                            { type: "danger", sticky: true }
                        );
                    });
                }

                if (result.ocr_data && result.ocr_data.length) {
                    result.ocr_data.forEach((item) => {
                        const data = {
                            ...item.data,
                            "辨識日期": new Date().toLocaleString(),
                        };
                        const dataStr = JSON.stringify(data, null, 2);
                        console.info(`[OCR原始格式] ${item.file}:\n${dataStr}`);
                        this.notification.add(
                            `【OCR原始格式】${item.file}：${dataStr}`,
                            { type: "info", sticky: true }
                        );
                    });
                }

                // 清空檔案清單
                this.state.files.splice(0);
            } else {
                this.notification.add(
                    result.message || "辨識失敗",
                    { type: "danger", sticky: true }
                );
            }
        } catch (e) {
            const error_msg = `辨識過程發生錯誤 : ${e.message}`;
            await this._logFrontendError(error_msg);
            this.notification.add(error_msg, { type: "danger", sticky: true });
        } finally {
            this.state.isProcessing = false;
        }
    }
}

/* =========================================================
 * 人類醫學 OCR
 * =======================================================*/
class IdxOcrPage1 extends IdxOcrBase {
    static template = "idx_ebs.ocr_page1";

    setup() {
        super.setup();
        this.state.submitUrl = "/idx_ocr/submit";
        this.state.page = "page1";
    }
}

/* =========================================================
 * 小動物 OCR
 * =======================================================*/
class IdxOcrPage2 extends IdxOcrBase {
    static template = "idx_ebs.ocr_page2";

    setup() {
        super.setup();
        this.state.submitUrl = "/idx_ocr/submit";
        this.state.page = "page2";
    }
}

/* =========================================================
 * Action 註冊
 * =======================================================*/
registry.category("actions").add("idx_ebs.ocr_page1", IdxOcrPage1);
registry.category("actions").add("idx_ebs.ocr_page2", IdxOcrPage2);
