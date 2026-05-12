odoo.define('idx_calendar.IDXCalendarPopover', function(require) {
    "use strict";

    const CalendarPopover = require('web.CalendarPopover');

    const IDXCalendarPopover = CalendarPopover.include({
        events: _.extend({}, CalendarPopover.prototype.events, {
            'click .o_cw_popover_copy': '_onClickPopoverCopy',
        }),

        _onClickPopoverCopy: function (ev) {
            ev.preventDefault();
            var self = this;

            return this._rpc({
                model: 'calendar.event',
                method: 'copy',
                args: [parseInt(this.event.id)],
            }).then(function (result) {
                self.trigger_up('edit_event', {
                    id: result,
                })
            });

        },
    })

    return IDXCalendarPopover;

});
