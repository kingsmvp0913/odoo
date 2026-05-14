/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { DetectsWidgetViewMixin } from "./detects_widget_view";

publicWidget.registry.detectsWidget = publicWidget.Widget.extend(Object.assign({}, DetectsWidgetViewMixin, {
    selector: '.detects_widget_container',
    events: {
        'click .report_qty_btn': '_onReportQtyClick',
    },

    async start() {
        await this._super(...arguments);
        await this._fetchDefaultPartnerName();
        this._initializeData();
        await this._fetchDatas();
        this._renderWidget();
    },

    async _fetchDefaultPartnerName() {
        try {
            const res = await fetch('/shop/report/default_partner_name', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            const response = await res.json();
            this.defaultPartnerName = response.success ? (response.partner_name || '') : '';
        } catch (error) {
            console.error('Failed to fetch default partner name:', error);
            this.defaultPartnerName = '';
        }
    },

    // 初始化數據
    _initializeData() {
        const el = this.el;
        this.cartId = el.dataset.cartId || '';
        this.cartLineId = el.dataset.cartLineId || '';
        this.category = el.dataset.category || '0';
        this.reportQty = 0;
        this.personDatas = {};
        this.animalDatas = {};
        this.tableClass = "detect_table table table-bordered table-striped table-hover text-center";
    },

    // 取得人類醫學送檢單資料
    async _fetchDatas() {
        if (!this.cartId || !this.cartLineId) {
            console.warn('No necessary params provided');
            return;
        }

        try {
            const url = `/shop/report/qty?cart_id=${this.cartId}&cart_line_id=${this.cartLineId}&category=${this.category}`;
            const res = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            const response = await res.json();

            if (response.success) {
                this.reportQty = response.report_qty || 0;
                this.personDatas = response.personDatas || {};
                this.animalDatas = response.animalDatas || {};
            } else {
                console.error('Failed to fetch report quantity:', response.error);
            }
        } catch (error) {
            console.error('Error during fetch call:', error);
        }
    },

    // 填寫檢測者按鈕渲染
    _renderWidget() {
        this.el.innerHTML = '';
        this.button = this._createElement('button', {
            className: 'btn btn-outline-primary report_qty_btn',
            textContent: `填寫檢測者 (${this.reportQty})`,
        });
        this.el.appendChild(this.button);
    },

    // 按鈕點擊事件處理
    _onReportQtyClick() {
        this.button.textContent = `填寫檢測者 (${this.reportQty})`;
        this._showTreeModal();
    },

    // 編輯行點擊事件處理
    _onEditRowClick(data) {
        this._showEditFormModal(data);
    },

    // 刪除行按鈕點擊事件處理
    async _onDeleteRowClick(e) {
        const reportId = e.currentTarget.dataset.personId;
        if (!reportId) {
            console.warn('No report ID provided');
            return;
        }

        if (!confirm('確定要刪除此筆送檢單紀錄？')) {
            return;
        }

        // 先取得 row 的引用
        const row = e.currentTarget.closest('tr');
        if (!row) {
            console.error('Cannot find table row');
            alert('無法找到要刪除的資料行！');
            return;
        }

        try {
            const res = await fetch(`/shop/report/delete?report_id=${reportId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

            const response = await res.json();

            if (response.success) {
                // 從 personDatas 或 animalDatas 中刪除對應的資料
                if (this.category === '0' && this.personDatas[this.cartLineId]) {
                    this.personDatas[this.cartLineId] = this.personDatas[this.cartLineId].filter(
                        person => person.report_id !== parseInt(reportId)
                    );
                } else if (this.category === '1' && this.animalDatas[this.cartLineId]) {
                    this.animalDatas[this.cartLineId] = this.animalDatas[this.cartLineId].filter(
                        animal => animal.report_id !== parseInt(reportId)
                    );
                }

                // 移除該行
                row.remove();

                // 更新報告數量
                this.reportQty = response.report_qty !== undefined ? response.report_qty : Math.max(0, this.reportQty - 1);

                // 更新按鈕文字
                if (this.button) {
                    this.button.textContent = `填寫檢測者 (${this.reportQty})`;
                }

            } else {
                alert(`刪除失敗: ${response.error || '未知錯誤'}`);
            }
        } catch (error) {
            console.error('刪除時發生錯誤:', error);
            alert(`刪除失敗: ${error.message}`);
        }
    },

    // 創建元素的輔助方法
    _createElement(tag, { className = '', textContent = '', attributes = {} } = {}) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (textContent) element.textContent = textContent;
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
        return element;
    },

    // 創建表格外層 wrapper
    _modalContentWrapper(content) {
        const wrapper = this._createElement('div', {
            className: 'modal-content-wrap',
        });
        wrapper.appendChild(content);
        return wrapper;
    },

    // 為表格列綁定事件
    _bindRowEvents(row, data) {
        // 綁定行點擊事件（編輯）
        row.addEventListener('click', (e) => {
            // 如果點擊的是刪除按鈕，不觸發編輯
            if (e.target.closest('.delete_row_btn')) return;
            this._onEditRowClick(data);
        });

        // 綁定刪除按鈕事件
        const deleteBtn = row.querySelector('.delete_row_btn');
        deleteBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this._onDeleteRowClick(e);
        });
    },

    _applyDefaultInspectionUnit(formWrapper) {
        const input = formWrapper?.querySelector('input[name="inspection_unit"]');
        if (!input || input.value || !this.defaultPartnerName) {
            return;
        }

        input.value = this.defaultPartnerName;
        input.defaultValue = this.defaultPartnerName;
    },

    // 動態添加新行到表格
    _addPersonRowToTable(modal, person) {
        const table = modal.querySelector('.person_template tbody');
        if (!table) return;

        const row = this._createElement('tr');
        row.dataset.reportId = person.report_id;
        row.innerHTML = this._generateRowHTML(person);
        this._bindRowEvents(row, person);
        table.insertBefore(row, table.firstChild);
    },

    // 動態添加新行到小動物表格
    _addAnimalRowToTable(modal, animal) {
        const table = modal.querySelector('.animal_template tbody');
        if (!table) return;

        const row = this._createElement('tr');
        row.dataset.reportId = animal.report_id;
        row.innerHTML = this._generateRowHTML(animal);
        this._bindRowEvents(row, animal);
        table.insertBefore(row, table.firstChild);
    },

    // 顯示編輯表單彈窗（支援人醫和小動物）
    _showEditFormModal(data) {
        const formOverlay = this._createElement('div', { className: 'modal_overlay' });
        const formModal = this._createElement('div', { className: 'detect_modal' });
        const formCloseWrap = this._createElement('div', {
            className: 'modal_close_btn_wrap',
        });
        const formCloseBtn = this._createElement('button', {
            className: 'modal_close_btn',
            textContent: '×',
        });

        // 根據 category 創建對應的表單並預填數據
        const form = this.category === '0'
            ? this._createPersonFormTemplate(data)
            : this._createAnimalFormTemplate(data);

        // 送出表單按鈕
        const formSubmitWrap = this._createElement('div', {
            className: 'modal_submit_btn_wrap w-100',
        });
        const formSubmitBtn = this._createElement('button', {
            className: 'modal_submit_btn btn btn-primary',
            textContent: '更新',
        });
        formSubmitWrap.appendChild(formSubmitBtn);

        // 送出表單事件
        formSubmitBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            await this._submitFormData(formModal, formOverlay, data.report_id);
        });

        // 關閉form彈窗事件
        formCloseBtn.addEventListener('click', () => formOverlay.remove());
        formOverlay.addEventListener('click', (e) => {
            if (e.target === formOverlay) formOverlay.remove();
        });

        formCloseWrap.appendChild(formCloseBtn);
        formModal.appendChild(formCloseWrap);
        formModal.appendChild(form);
        formModal.appendChild(formSubmitWrap);
        formOverlay.appendChild(formModal);
        document.body.appendChild(formOverlay);
    },

    // 收集並提交表單數據（支援新增和更新）
    async _submitFormData(formModalElement, overlayElement, reportId = null, treeModal = null) {
        const formData = new FormData(formModalElement.querySelector('form'));
        const isUpdate = reportId !== null;
        const data = {
            cart_id: this.cartId,
            cart_line_id: this.cartLineId,
            category: this.category,
        };

        // 如果是更新操作，加入 report_id
        if (isUpdate) {
            data.report_id = reportId;
        }

        // 將表單數據轉換為物件（處理 checkbox 複選值）
        formData.forEach((value, key) => {
            if (key === 'skin_symptom_ids') {
                data[key] = data[key] ? [...data[key], value] : [value];
            } else {
                data[key] = value;
            }
        });

        try {
            const url = isUpdate ? '/shop/report/update' : '/shop/report/create';
            const method = isUpdate ? 'PUT' : 'POST';

            const res = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

            const response = await res.json();

            if (response.success) {
                // 關閉表單彈窗
                overlayElement.remove();

                if (isUpdate) {
                    // 更新操作：更新本地資料並重新渲染表格
                    const dataStore = this.category === '0' ? this.personDatas : this.animalDatas;
                    if (dataStore[this.cartLineId]) {
                        const index = dataStore[this.cartLineId].findIndex(
                            item => item.report_id === parseInt(reportId)
                        );
                        if (index !== -1) {
                            dataStore[this.cartLineId][index] = this._buildResponseData(response, reportId);
                        }
                    }

                    // 重新渲染表格
                    const treeModal = document.querySelector('.detect_modal');
                    if (treeModal) {
                        const tableWrapper = treeModal.querySelector('.modal-content-wrap');
                        if (tableWrapper) {
                            tableWrapper.remove();
                            const newTable = this.category === '0'
                                ? this._createPersonTemplate()
                                : this._createAnimalTemplate();
                            const createBtn = treeModal.querySelector('.modal_create_btn');
                            if (createBtn && createBtn.nextSibling) {
                                treeModal.insertBefore(newTable, createBtn.nextSibling);
                            } else {
                                treeModal.appendChild(newTable);
                            }
                        }
                    }
                } else {
                    // 新增操作：更新報告數量並添加新行
                    this.reportQty = response.report_qty || this.reportQty + 1;
                    this.button.textContent = `填寫檢測者 (${this.reportQty})`;

                    const newData = this._buildResponseData(response);
                    const dataStore = this.category === '0' ? this.personDatas : this.animalDatas;

                    if (!dataStore[this.cartLineId]) {
                        dataStore[this.cartLineId] = [];
                    }
                    dataStore[this.cartLineId].unshift(newData);

                    // 動態添加新行到表格
                    if (this.category === '0') {
                        this._addPersonRowToTable(treeModal, newData);
                    } else {
                        this._addAnimalRowToTable(treeModal, newData);
                    }
                }
            } else {
                alert(`${isUpdate ? '更新' : '提交'}失敗: ${response.error || '未知錯誤'}`);
            }
        } catch (error) {
            console.error(`${isUpdate ? '更新' : '提交'}送檢單時發生錯誤:`, error);
            alert(`${isUpdate ? '更新' : '提交'}失敗: ${error.message}`);
        }
    },

    // 從 response 建構資料物件
    _buildResponseData(response, reportId = null) {
        const baseData = {
            report_id: reportId || response.report_id || '',
            product_template_id: response.requisition.product_template_id || '',
            internal_note: response.requisition.internal_note || '',
            patient_name: response.requisition.patient_name || '',
            gender: response.requisition.gender || '',
        };

        if (this.category === '0') {
            // 人類醫學資料
            return {
                ...baseData,
                inspection_unit: response.requisition.inspection_unit || '',
                medical_no: response.requisition.medical_no || '',
                birth_date: response.requisition.birth_date || '',
                sample_type: response.requisition.sample_type || '',
                note: response.requisition.note || '',
            };
        } else {
            // 小動物資料
            return {
                ...baseData,
                partner_id: response.requisition.partner_id || '',
                doctor_name: response.requisition.doctor_name || '',
                partner_address: response.requisition.partner_address || '',
                partner_email: response.requisition.partner_email || '',
                partner_phone: response.requisition.partner_phone || '',
                owner_name: response.requisition.owner_name || '',
                animal_type: response.requisition.animal_type || '',
                breed: response.requisition.breed || '',
                weight: response.requisition.weight || 0,
                collect_date: response.requisition.collect_date || '',
                neutered: response.requisition.neutered || false,
                age: response.requisition.age || "",
                has_other_animals: response.requisition.has_other_animals || false,
                other_animals_count: response.requisition.other_animals_count || 0,
                flea_history: response.requisition.flea_history || '',
                environment_changed: response.requisition.environment_changed || false,
                environment_change_desc: response.requisition.environment_change_desc || '',
                first_onset_age: response.requisition.first_onset_age || "",
                recurrent_years: response.requisition.recurrent_years || false,
                recurrent_duration: response.requisition.recurrent_duration || '',
                symptom_type: response.requisition.symptom_type || '',
                long_term_attack: response.requisition.long_term_attack || false,
                skin_symptom_ids: response.requisition.skin_symptom_ids || [],
                parasite_type: response.requisition.parasite_type || '',
                secondary_infection: response.requisition.secondary_infection || '',
                symptom_period: response.requisition.symptom_period || '',
                severe_season: response.requisition.severe_season || '',
                severe_months: response.requisition.severe_months || '',
                corticosteroids_note: response.requisition.corticosteroids_note || '',
                corticosteroids_last_date: response.requisition.corticosteroids_last_date || '',
                corticosteroids_effect: response.requisition.corticosteroids_effect || '',
                antihistamine_note: response.requisition.antihistamine_note || '',
                antihistamine_last_date: response.requisition.antihistamine_last_date || '',
                antihistamine_effect: response.requisition.antihistamine_effect || '',
                antibiotics_note: response.requisition.antibiotics_note || '',
                antibiotics_last_date: response.requisition.antibiotics_last_date || '',
                antibiotics_effect: response.requisition.antibiotics_effect || '',
                antifungal_note: response.requisition.antifungal_note || '',
                antifungal_last_date: response.requisition.antifungal_last_date || '',
                antifungal_effect: response.requisition.antifungal_effect || '',
                other_med_note: response.requisition.other_med_note || '',
                other_med_last_date: response.requisition.other_med_last_date || '',
                other_med_effect: response.requisition.other_med_effect || '',
            };
        }
    },

    // 檢測單 Tree 彈窗
    _showTreeModal() {
        const overlay = this._createElement('div', { className: 'modal_overlay' });
        const modal = this._createElement('div', { className: 'detect_modal' });
        const closeBtnWrap = this._createElement('div', {
            className: 'modal_close_btn_wrap',
        });
        const closeBtn = this._createElement('button', {
            className: 'modal_close_btn',
            textContent: '×',
        });
        const createBtn = this._createElement('button', {
            className: 'modal_create_btn btn btn-primary',
            textContent: '新增',
        });

        // 根據類別添加對應表格
        const treeMap = {
            "0": () => this._createPersonTemplate(),
            "1": () => this._createAnimalTemplate(),
        };
        // 根據類別添加對應表單
        const formMap = {
            "0": () => this._createPersonFormTemplate(),
            "1": () => this._createAnimalFormTemplate(),
        };

        const table = treeMap[this.category]?.() || null;
        const form = formMap[this.category]?.() || null;

        // 關閉Tree彈窗事件
        closeBtn.addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        // 新增表單紀錄事件
        createBtn.addEventListener('click', () => {
            form.querySelector('form').reset();
            this._applyDefaultInspectionUnit(form);
            // 再疊一層彈窗，內容是form
            const formOverlay = this._createElement('div', { className: 'modal_overlay' });
            const formModal = this._createElement('div', { className: 'detect_modal' });
            const formCloseWrap = this._createElement('div', {
                className: 'modal_close_btn_wrap',
            });
            const formCloseBtn = this._createElement('button', {
                className: 'modal_close_btn',
                textContent: '×',
            });
            // 送出表單按鈕
            const formSubmitWrap = this._createElement('div', {
                className: 'modal_submit_btn_wrap w-100',
            });
            const formSubmitBtn = this._createElement('button', {
                className: 'modal_submit_btn btn btn-primary',
                textContent: '送出',
            });
            formSubmitWrap.appendChild(formSubmitBtn);

            // 送出表單事件
            formSubmitBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                await this._submitFormData(formModal, formOverlay, null, modal);
            });

            // 關閉form彈窗事件
            formCloseBtn.addEventListener('click', () => formOverlay.remove());
            formOverlay.addEventListener('click', (e) => {
                if (e.target === formOverlay) formOverlay.remove();
            });
            formCloseWrap.appendChild(formCloseBtn);
            formModal.appendChild(formCloseWrap);
            if (form) {
                formModal.appendChild(form);
            }

            formModal.appendChild(formSubmitWrap);
            formOverlay.appendChild(formModal);
            document.body.appendChild(formOverlay);
        });

        closeBtnWrap.appendChild(closeBtn);
        modal.appendChild(closeBtnWrap);
        modal.appendChild(createBtn);
        if (table) {
            modal.appendChild(table);
        }
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    },
}));

// 使用 MutationObserver 監聽購物車 DOM 變化並重新初始化 widget
(function () {
    const initDetectsWidgets = () => {
        document.querySelectorAll('.detects_widget_container').forEach((el) => {
            if (!el.__detectsWidgetInitialized) {
                const widget = new publicWidget.registry.detectsWidget(null, {});
                widget.setElement(el);
                widget.start();
                el.__detectsWidgetInitialized = true;
            }
        });
    };

    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length > 0) {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // 元素節點
                        // 檢查新增的節點本身或其子節點是否包含 detects_widget_container
                        if (node.classList?.contains('detects_widget_container')) {
                            const widget = new publicWidget.registry.detectsWidget(null, {});
                            widget.setElement(node);
                            widget.start();
                            node.__detectsWidgetInitialized = true;
                        } else if (node.querySelectorAll) {
                            const containers = node.querySelectorAll('.detects_widget_container');
                            containers.forEach((el) => {
                                if (!el.__detectsWidgetInitialized) {
                                    const widget = new publicWidget.registry.detectsWidget(null, {});
                                    widget.setElement(el);
                                    widget.start();
                                    el.__detectsWidgetInitialized = true;
                                }
                            });
                        }
                    }
                });
            }
        });
    });

    // 等待 DOM 載入完成後開始監聽
    const startObserving = () => {
        const cartContainer = document.querySelector('#cart_products');
        if (cartContainer && cartContainer.parentElement) {
            observer.observe(cartContainer.parentElement, {
                childList: true,
                subtree: true
            });
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserving);
    } else {
        startObserving();
    }
})();

export default publicWidget.registry.detectsWidget;
