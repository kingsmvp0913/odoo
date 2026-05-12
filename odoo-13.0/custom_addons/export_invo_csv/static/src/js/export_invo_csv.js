odoo.define('export_invo_csv.ListController', function (require) {
    'use strict';

    var ListController = require('web.ListController');

    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (this.$buttons) {
                this.$buttons.on(
                    'click',
                    '.o_list_export_invo_csv',
                    this._onExportInvoCsv.bind(this)
                );
            }
        },

        _onExportInvoCsv: function (ev) {
            ev.preventDefault();
            var state = this.model.get(this.handle, {raw: true});
            var domain = state.domain || [];
            var url = '/export_invo_csv/download?domain=' +
                encodeURIComponent(JSON.stringify(domain));
            window.location.href = url;
        },
    });
});
