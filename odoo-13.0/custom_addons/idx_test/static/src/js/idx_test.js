odoo.define('idx_test.FormController', function (require) {
    'use strict';

    var FormController = require('web.FormController');

    FormController.include({
        /**
         * Override getTitle to append @@@@ to the breadcrumb title
         * when the current model is account.move.
         *
         * @override
         * @returns {string}
         */
        getTitle: function () {
            var title = this._super.apply(this, arguments);
            if (this.modelName === 'account.move') {
                title = title + ' @@@@';
            }
            return title;
        },
    });
});
