/** @odoo-module **/

/**
 * 檢測 Widget 視圖模板模組
 * 包含所有模板渲染相關的方法
 */
export const DetectsWidgetViewMixin = {
    // 產生檢測資料列的 HTML（支援人醫和小動物）
    _generateRowHTML(data) {
        if (this.category === '0') {
            const genderMap = { 'male': '男', 'female': '女', 'other': '其他', 'unknown': '不提供' };
            const typeMap = { 'serum': '血清', 'plasma': '血漿' };
            return `
                <td>${data.product_template_id || '-'}</td>
                <td>${data.internal_note || '-'}</td>
                <td>${data.inspection_unit || '-'}</td>
                <td>${data.patient_name || '-'}</td>
                <td>${genderMap[data.gender] || data.gender || '-'}</td>
                <td>${data.medical_no || '-'}</td>
                <td>${data.birth_date || '-'}</td>
                <td>${typeMap[data.sample_type] || data.sample_type || '-'}</td>
                <td>${data.note || '-'}</td>
                <td>
                    <button class="btn btn-sm delete_row_btn" data-person-id="${data.report_id || ''}">
                        <i class="fa fa-trash"></i>
                    </button>
                </td>
            `;
        } else {
            const genderMap = { 'male': '公', 'female': '母' };
            const typeMap = { 'dog': '犬', 'cat': '貓' };
            return `
                <td>${data.product_template_id || '-'}</td>
                <td>${data.internal_note || '-'}</td>
                <td>${data.partner_id || '-'}</td>
                <td>${data.doctor_name || '-'}</td>
                <td>${data.partner_address || '-'}</td>
                <td>${data.partner_email || '-'}</td>
                <td>${data.partner_phone || '-'}</td>
                <td>${data.patient_name || '-'}</td>
                <td>${data.owner_name || '-'}</td>
                <td>${typeMap[data.animal_type] || data.animal_type || '-'}</td>
                <td>${data.collect_date || '-'}</td>
                <td>${genderMap[data.gender] || data.gender || '-'}</td>
                <td>${data.neutered ? '是' : '否'}</td>
                <td>
                    <button class="btn btn-sm delete_row_btn" data-person-id="${data.report_id || ''}">
                        <i class="fa fa-trash"></i>
                    </button>
                </td>
            `;
        }
    },

    // 【人類醫學】表格樣板
    _createPersonTemplate() {
        const table = this._createElement('table', {
            className: `person_template ${this.tableClass}`
        });
        table.innerHTML = `
            <thead class="table-primary">
                <tr>
                    <th>檢測項目<br>Testing Panel</th>
                    <th>檢測備註<br>Testing Notes</th>
                    <th>送檢單位<br>Institution Name</th>
                    <th>姓名<br>Name</th>
                    <th>性別<br>Gender</th>
                    <th>病歷號碼/採檢卡號<br>Patient ID/Blood Spot Card No.</th>
                    <th>出生年月日<br>Date of Birth</th>
                    <th>樣本種類<br>Specimens Type</th>
                    <th>備註<br>Remark</th>
                    <th>操作<br>Operate</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        `;

        // 動態填充 tbody 內容
        const tbody = table.querySelector('tbody');
        const personDatasList = this.personDatas[this.cartLineId] || [];

        personDatasList.forEach((person) => {
            const row = this._createElement('tr');
            row.dataset.reportId = person.report_id;
            row.innerHTML = this._generateRowHTML(person);
            this._bindRowEvents(row, person);
            tbody.appendChild(row);
        });

        return this._modalContentWrapper(table);
    },

    // 【人類醫學】表單樣板
    _createPersonFormTemplate(personData = null) {
        const defaultName = personData?.inspection_unit || this.defaultPartnerName || '';
        const form = this._createElement('form', {
            className: 'form_template person_form_template',
        });
        form.innerHTML = `
            <div class="form-item">
                <label for="patient_name" class="form-label text-primary">姓名<br>Name</label>
                <input type="text" class="form-control" name="patient_name" id="patient_name" value="${personData?.patient_name || ''}">
            </div>
            <div class="form-item">
                <label for="gender" class="form-label text-primary">性別<br>Gender</label>
                <select class="form-select" name="gender" id="gender">
                    <option value="male" ${personData?.gender === 'male' ? 'selected' : ''}>男</option>
                    <option value="female" ${personData?.gender === 'female' ? 'selected' : ''}>女</option>
                    <option value="other" ${personData?.gender === 'other' ? 'selected' : ''}>其他</option>
                    <option value="unknown" ${personData?.gender === 'unknown' ? 'selected' : ''}>不提供</option>
                </select>
            </div>
            <div class="form-item">
                <label for="birth_date" class="form-label text-primary">出生年月日<br>Date of Birth</label>
                <input type="date" class="form-control" name="birth_date" id="birth_date" value="${personData?.birth_date || ''}">
            </div>
            <div class="form-item">
                <label for="medical_no" class="form-label text-primary">病歷號碼/採檢卡號<br>Patient ID/Blood Spot Card No.</label>
                <input type="text" class="form-control" name="medical_no" id="medical_no" value="${personData?.medical_no || ''}">
            </div>
            <div class="form-item">
                <label for="sample_type" class="form-label text-primary">樣本種類<br>Specimens Type</label>
                <select class="form-select" name="sample_type" id="sample_type">
                    <option value="">請選擇</option>
                    <option value="serum" ${personData?.sample_type === 'serum' ? 'selected' : ''}>血清</option>
                    <option value="plasma" ${personData?.sample_type === 'plasma' ? 'selected' : ''}>血漿</option>
                </select>
            </div>
            <div class="form-item">
                <label for="inspection_unit" class="form-label text-primary">送檢單位<br>Institution Name</label>
                <input type="text" class="form-control" name="inspection_unit" id="inspection_unit" value="${defaultName}">
            </div>
            <div class="form-item">
                <label for="note" class="form-label text-primary">備註<br>Remark</label>
                <input type="text" class="form-control" name="note" id="note" value="${personData?.note || ''}">
            </div>
        `;
        return this._modalContentWrapper(form);
    },

    // 【小動物】表格樣板
    _createAnimalTemplate() {
        const table = this._createElement('table', {
            className: `animal_template ${this.tableClass}`
        });
        table.innerHTML = `
            <thead class="table-primary">
                <tr>
                    <th>檢測項目<br>Test Type</th>
                    <th>檢測備註<br>Test Notes</th>
                    <th>送檢醫院<br>Name of Clinic</th>
                    <th>送檢醫生<br>Name of Vet</th>
                    <th>醫院地址<br>Clinic address</th>
                    <th>Email</th>
                    <th>電話<br>Phone# of Clinic</th>
                    <th>病患名稱<br>Name of Pet</th>
                    <th>飼主姓名<br>Name of Owner</th>
                    <th>物種<br>Breed</th>
                    <th>採血日期<br>Date of sampling</th>
                    <th>性別<br>Sex</th>
                    <th>絕育<br>Spay/Neuter</th>
                    <th>操作<br>Operate</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        `;

        // 動態填充 tbody 內容
        const tbody = table.querySelector('tbody');
        const animalDatasList = this.animalDatas[this.cartLineId] || [];

        animalDatasList.forEach((animal) => {
            const row = this._createElement('tr');
            row.dataset.reportId = animal.report_id;
            row.innerHTML = this._generateRowHTML(animal);
            this._bindRowEvents(row, animal);
            tbody.appendChild(row);
        });

        return this._modalContentWrapper(table);
    },

    // 【小動物】表單樣板
    _createAnimalFormTemplate(personData = null) {
        const form = this._createElement('form', {
            className: 'form_template animal_form_template',
        });
        form.innerHTML = `
            <div class="form-item">
                <label for="doctor_name" class="form-label text-primary">送檢醫師<br>Name of Vet</label>
                <input type="text" class="form-control" name="doctor_name" id="doctor_name" value="${personData?.doctor_name || ''}">
            </div>
            <div class="form-item">
                <label for="patient_name" class="form-label text-primary">病患名稱<br>Name of Pet</label>
                <input type="text" class="form-control" name="patient_name" id="patient_name" value="${personData?.patient_name || ''}">
            </div>
            <div class="form-item">
                <label for="owner_name" class="form-label text-primary">飼主姓名<br>Name of Owner</label>
                <input type="text" class="form-control" name="owner_name" id="owner_name" value="${personData?.owner_name || ''}">
            </div>
            <div class="form-item">
                <label for="animal_type" class="form-label text-primary">物種<br>Species</label>
                <select class="form-select" name="animal_type" id="animal_type">
                    <option value="dog" ${personData?.animal_type === 'dog' ? 'selected' : ''}>犬</option>
                    <option value="cat" ${personData?.animal_type === 'cat' ? 'selected' : ''}>貓</option>
                </select>
            </div>
            <div class="form-item">
                <label for="breed" class="form-label text-primary">品系<br>Breed</label>
                <input type="text" class="form-control" name="breed" id="breed" value="${personData?.breed || ''}">
            </div>
            <div class="form-item">
                <label for="weight" class="form-label text-primary">體重(kg)</label>
                <input type="number" step="0.01" class="form-control" name="weight" id="weight" value="${personData?.weight || ''}">
            </div>
            <div class="form-item">
                <label for="collect_date" class="form-label text-primary">採血日期<br>Date of sampling</label>
                <input type="date" class="form-control" name="collect_date" id="collect_date" value="${personData?.collect_date || ''}">
            </div>
            <div class="form-item">
                <label for="gender" class="form-label text-primary">性別<br>Sex</label>
                <select class="form-select" name="gender" id="gender">
                    <option value="male" ${personData?.gender === 'male' ? 'selected' : ''}>公</option>
                    <option value="female" ${personData?.gender === 'female' ? 'selected' : ''}>母</option>
                </select>
            </div>
            <div class="form-item">
                <label for="neutered" class="form-label text-primary">絕育<br>Spay/Neuter</label>
                <select class="form-select" name="neutered" id="neutered">
                    <option value="true" ${personData?.neutered ? 'selected' : ''}>是</option>
                    <option value="false" ${personData?.neutered === false ? 'selected' : ''}>否</option>
                </select>
            </div>
            <div class="form-item">
                <label for="age" class="form-label text-primary">年齡(yo)</label>
                <input type="text" class="form-control" name="age" id="age" value="${personData?.age || ''}">
            </div>
            <div class="form-item full check-box-area has_under_input pt-4 border-top">
                <label class="form-label text-primary">家中是否有飼養其他動物</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="has_other_animals" id="has_other_animals_yes" value="true" ${personData?.has_other_animals ? 'checked' : ''}>
                        <label class="form-check-label" for="has_other_animals_yes">是</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="has_other_animals" id="has_other_animals_no" value="false" ${personData?.has_other_animals === false ? 'checked' : ''}>
                        <label class="form-check-label" for="has_other_animals_no">否</label>
                    </div>
                </div>
                <div class="form-sub-item">
                    <label for="other_animals_count" class="form-label text-primary">若是, 則物種與數量為</label>
                    <input type="number" class="form-control" name="other_animals_count" id="other_animals_count" value="${personData?.other_animals_count || ''}">
                </div>
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">是否有跳蚤病史</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="flea_history" id="flea_history_infected" value="infected" ${personData?.flea_history === 'infected' ? 'checked' : ''}>
                        <label class="form-check-label" for="flea_history_infected">是(正在感染)</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="flea_history" id="flea_history_treated" value="treated" ${personData?.flea_history === 'treated' ? 'checked' : ''}>
                        <label class="form-check-label" for="flea_history_treated">是(已除蚤)</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="flea_history" id="flea_history_no" value="no" ${personData?.flea_history === 'no' ? 'checked' : ''}>
                        <label class="form-check-label" for="flea_history_no">否</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="flea_history" id="flea_history_unknown" value="unknown" ${personData?.flea_history === 'unknown' ? 'checked' : ''}>
                        <label class="form-check-label" for="flea_history_unknown">不確定</label>
                    </div>
                </div>
            </div>
            <div class="form-item full check-box-area has_under_input">
                <label class="form-label text-primary">生活環境改變</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="environment_changed" id="environment_changed_yes" value="true" ${personData?.environment_changed ? 'checked' : ''}>
                        <label class="form-check-label" for="environment_changed_yes">是</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="environment_changed" id="environment_changed_no" value="false" ${personData?.environment_changed === false ? 'checked' : ''}>
                        <label class="form-check-label" for="environment_changed_no">否</label>
                    </div>
                </div>
                <div class="form-sub-item">
                    <label for="environment_change_desc" class="form-label text-primary">若是，則簡述環境變化(如由市中心遷居近郊)</label>
                    <input type="text" class="form-control" name="environment_change_desc" id="environment_change_desc" value="${personData?.environment_change_desc || ''}">
                </div>
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">第一次發作之年齡為</label>
                <input type="text" class="form-control" name="first_onset_age" id="first_onset_age" value="${personData?.first_onset_age || ''}">
            </div>
            <div class="form-item full check-box-area has_under_input">
                <label class="form-label text-primary">反覆發作數年</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="recurrent_years" id="recurrent_years_yes" value="true" ${personData?.recurrent_years ? 'checked' : ''}>
                        <label class="form-check-label" for="recurrent_years_yes">是</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="recurrent_years" id="recurrent_years_no" value="false" ${personData?.recurrent_years === false ? 'checked' : ''}>
                        <label class="form-check-label" for="recurrent_years_no">否</label>
                    </div>
                </div>
                <div class="form-sub-item">
                    <label for="recurrent_duration" class="form-label text-primary">若是，則持續多久</label>
                    <input type="text" class="form-control" name="recurrent_duration" id="recurrent_duration" value="${personData?.recurrent_duration || ''}">
                </div>
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">主要臨床症狀為何種類型</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="symptom_type" id="symptom_type_skin" value="skin" ${personData?.symptom_type === 'skin' ? 'checked' : ''}>
                        <label class="form-check-label" for="symptom_type_skin">皮膚型</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="symptom_type" id="symptom_type_respiratory" value="respiratory" ${personData?.symptom_type === 'respiratory' ? 'checked' : ''}>
                        <label class="form-check-label" for="symptom_type_respiratory">呼吸道</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="symptom_type" id="symptom_type_digestive" value="digestive" ${personData?.symptom_type === 'digestive' ? 'checked' : ''}>
                        <label class="form-check-label" for="symptom_type_digestive">消化道</label>
                    </div>
                </div>
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">一年至少有三個月以上發作期</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="long_term_attack" id="long_term_attack_yes" value="true" ${personData?.long_term_attack ? 'checked' : ''}>
                        <label class="form-check-label" for="long_term_attack_yes">是</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="long_term_attack" id="long_term_attack_no" value="false" ${personData?.long_term_attack === false ? 'checked' : ''}>
                        <label class="form-check-label" for="long_term_attack_no">否</label>
                    </div>
                </div>
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary mb-auto">皮膚症狀包括</label>
                <div class="form-check-group">
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_itch" value="搔癢" ${personData?.skin_symptom_ids?.includes('搔癢') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_itch">搔癢</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_hair_loss" value="脫毛" ${personData?.skin_symptom_ids?.includes('脫毛') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_hair_loss">脫毛</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_rash" value="皮膚紅疹" ${personData?.skin_symptom_ids?.includes('皮膚紅疹') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_rash">皮膚紅疹</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_interdigital" value="趾間炎" ${personData?.skin_symptom_ids?.includes('趾間炎') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_interdigital">趾間炎</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_otitis" value="耳炎" ${personData?.skin_symptom_ids?.includes('耳炎') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_otitis">耳炎</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_crust" value="結痂" ${personData?.skin_symptom_ids?.includes('結痂') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_crust">結痂</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_scratching" value="抓癢" ${personData?.skin_symptom_ids?.includes('抓癢') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_scratching">抓癢</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_lichenification" value="苔癬化" ${personData?.skin_symptom_ids?.includes('苔癬化') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_lichenification">苔癬化</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_papule" value="丘疹" ${personData?.skin_symptom_ids?.includes('丘疹') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_papule">丘疹</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_pustule" value="膿皰" ${personData?.skin_symptom_ids?.includes('膿皰') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_pustule">膿皰</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_pyoderma" value="膿皮症" ${personData?.skin_symptom_ids?.includes('膿皮症') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_pyoderma">膿皮症</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_seborrhea" value="脂漏性皮膚炎" ${personData?.skin_symptom_ids?.includes('脂漏性皮膚炎') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_seborrhea">脂漏性皮膚炎</label>
                    </div>
                    <div class="form-check multi">
                        <input class="form-check-input" type="checkbox" name="skin_symptom_ids" id="skin_symptom_malassezia" value="皮屑芽孢菌(馬拉色菌)" ${personData?.skin_symptom_ids?.includes('皮屑芽孢菌(馬拉色菌)') ? 'checked' : ''}>
                        <label class="form-check-label" for="skin_symptom_malassezia">皮屑芽孢菌(馬拉色菌)</label>
                    </div>
                </div>
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">外寄生蟲(種別)</label>
                <input type="text" class="form-control" name="parasite_type" id="parasite_type" value="${personData?.parasite_type || ''}">
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">繼發性感染(病原)</label>
                <input type="text" class="form-control" name="secondary_infection" id="secondary_infection" value="${personData?.secondary_infection || ''}">
            </div>
            <div class="form-item full check-box-area">
                <label class="form-label text-primary">臨床症狀好發期</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="symptom_period" id="symptom_type_seasonal" value="seasonal" ${personData?.symptom_period === 'seasonal' ? 'checked' : ''}>
                        <label class="form-check-label" for="symptom_type_seasonal">季節性</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="symptom_period" id="symptom_type_non_seasonal" value="non_seasonal" ${personData?.symptom_period === 'non_seasonal' ? 'checked' : ''}>
                        <label class="form-check-label" for="symptom_type_non_seasonal">非季節性(整年都有)</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="symptom_period" id="symptom_type_specific" value="specific" ${personData?.symptom_period === 'specific' ? 'checked' : ''}>
                        <label class="form-check-label" for="symptom_type_specific">非季節性但特定季節更嚴重</label>
                    </div>
                </div>
            </div>
            <div class="form-item full check-box-area has_under_input">
                <label class="form-label text-primary">在什麼季節或特定期間症狀最為嚴重</label>
                <div class="form-check-group">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="severe_season" id="severe_season_spring" value="spring" ${personData?.severe_season === 'spring' ? 'checked' : ''}>
                        <label class="form-check-label" for="severe_season_spring">春季</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="severe_season" id="severe_season_summer" value="summer" ${personData?.severe_season === 'summer' ? 'checked' : ''}>
                        <label class="form-check-label" for="severe_season_summer">夏季</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="severe_season" id="severe_season_autumn" value="autumn" ${personData?.severe_season === 'autumn' ? 'checked' : ''}>
                        <label class="form-check-label" for="severe_season_autumn">秋季</label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="severe_season" id="severe_season_winter" value="winter" ${personData?.severe_season === 'winter' ? 'checked' : ''}>
                        <label class="form-check-label" for="severe_season_winter">冬季</label>
                    </div>
                </div>
                <div class="form-sub-item">
                    <label for="severe_months" class="form-label text-primary">或哪些月份特別嚴重</label>
                    <input type="text" class="form-control" name="severe_months" id="severe_months" value="${personData?.severe_months || ''}">
                </div>
            </div>
            <div class="form-item full table-area">
                <label class="form-label text-primary">六個月內用藥史</label>
                <label class="form-label text-primary">藥物成分名、劑量和給予途徑</label>
                <label class="form-label text-primary">最後一次給藥時間</label>
                <label class="form-label text-primary">改善/無感/惡化</label>
            </div>
            <div class="form-item full table-area">
                <div>
                    <label class="form-label text-primary">Corticosteroids：</label>
                </div>
                <div>
                    <label class="form-label text-primary d-none">藥物成分名、劑量和給予途徑</label>
                    <input type="text" class="form-control" name="corticosteroids_note" id="corticosteroids_note" value="${personData?.corticosteroids_note || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">最後一次給藥時間</label>
                    <input type="text" class="form-control" name="corticosteroids_last_date" id="corticosteroids_last_date" value="${personData?.corticosteroids_last_date || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">改善/無感/惡化</label>
                    <select class="form-select" name="corticosteroids_effect" id="corticosteroids_effect">
                        <option value="">請選擇</option>
                        <option value="better" ${personData?.corticosteroids_effect === 'better' ? 'selected' : ''}>改善</option>
                        <option value="same" ${personData?.corticosteroids_effect === 'same' ? 'selected' : ''}>無感</option>
                        <option value="worse" ${personData?.corticosteroids_effect === 'worse' ? 'selected' : ''}>惡化</option>
                    </select>
                </div>
            </div>
            <div class="form-item full table-area">
                <div>
                    <label class="form-label text-primary">Antihistamine：</label>
                </div>
                <div>
                    <label class="form-label text-primary d-none">藥物成分名、劑量和給予途徑</label>
                    <input type="text" class="form-control" name="antihistamine_note" id="antihistamine_note" value="${personData?.antihistamine_note || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">最後一次給藥時間</label>
                    <input type="text" class="form-control" name="antihistamine_last_date" id="antihistamine_last_date" value="${personData?.antihistamine_last_date || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">改善/無感/惡化</label>
                    <select class="form-select" name="antihistamine_effect" id="antihistamine_effect">
                        <option value="">請選擇</option>
                        <option value="better" ${personData?.antihistamine_effect === 'better' ? 'selected' : ''}>改善</option>
                        <option value="same" ${personData?.antihistamine_effect === 'same' ? 'selected' : ''}>無感</option>
                        <option value="worse" ${personData?.antihistamine_effect === 'worse' ? 'selected' : ''}>惡化</option>
                    </select>
                </div>
            </div>
            <div class="form-item full table-area">
                <div>
                    <label class="form-label text-primary">Antibiotics：</label>
                </div>
                <div>
                    <label class="form-label text-primary d-none">藥物成分名、劑量和給予途徑</label>
                    <input type="text" class="form-control" name="antibiotics_note" id="antibiotics_note" value="${personData?.antibiotics_note || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">最後一次給藥時間</label>
                    <input type="text" class="form-control" name="antibiotics_last_date" id="antibiotics_last_date" value="${personData?.antibiotics_last_date || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">改善/無感/惡化</label>
                    <select class="form-select" name="antibiotics_effect" id="antibiotics_effect">
                        <option value="">請選擇</option>
                        <option value="better" ${personData?.antibiotics_effect === 'better' ? 'selected' : ''}>改善</option>
                        <option value="same" ${personData?.antibiotics_effect === 'same' ? 'selected' : ''}>無感</option>
                        <option value="worse" ${personData?.antibiotics_effect === 'worse' ? 'selected' : ''}>惡化</option>
                    </select>
                </div>
            </div>
            <div class="form-item full table-area">
                <div>
                    <label class="form-label text-primary">Antifungal agents：</label>
                </div>
                <div>
                    <label class="form-label text-primary d-none">藥物成分名、劑量和給予途徑</label>
                    <input type="text" class="form-control" name="antifungal_note" id="antifungal_note" value="${personData?.antifungal_note || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">最後一次給藥時間</label>
                    <input type="text" class="form-control" name="antifungal_last_date" id="antifungal_last_date" value="${personData?.antifungal_last_date || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">改善/無感/惡化</label>
                    <select class="form-select" name="antifungal_effect" id="antifungal_effect">
                        <option value="">請選擇</option>
                        <option value="better" ${personData?.antifungal_effect === 'better' ? 'selected' : ''}>改善</option>
                        <option value="same" ${personData?.antifungal_effect === 'same' ? 'selected' : ''}>無感</option>
                        <option value="worse" ${personData?.antifungal_effect === 'worse' ? 'selected' : ''}>惡化</option>
                    </select>
                </div>
            </div>
            <div class="form-item full table-area">
                <div>
                    <label class="form-label text-primary">Others：</label>
                </div>
                <div>
                    <label class="form-label text-primary d-none">藥物成分名、劑量和給予途徑</label>
                    <input type="text" class="form-control" name="other_med_note" id="other_med_note" value="${personData?.other_med_note || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">最後一次給藥時間</label>
                    <input type="text" class="form-control" name="other_med_last_date" id="other_med_last_date" value="${personData?.other_med_last_date || ''}">
                </div>
                <div>
                    <label class="form-label text-primary d-none">改善/無感/惡化</label>
                    <select class="form-select" name="other_med_effect" id="other_med_effect">
                        <option value="">請選擇</option>
                        <option value="better" ${personData?.other_med_effect === 'better' ? 'selected' : ''}>改善</option>
                        <option value="same" ${personData?.other_med_effect === 'same' ? 'selected' : ''}>無感</option>
                        <option value="worse" ${personData?.other_med_effect === 'worse' ? 'selected' : ''}>惡化</option>
                    </select>
                </div>
            </div>
        `;
        return this._modalContentWrapper(form);
    },
};

export default DetectsWidgetViewMixin;
