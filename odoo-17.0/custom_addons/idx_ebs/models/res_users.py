from odoo import api, models, _, fields
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from lxml import etree
from lxml.builder import E
from odoo.addons.base.models.res_users import name_selection_groups, name_boolean_group

class ResUsers(models.Model):
    _inherit = "res.users"
    
    @api.model
    def default_get(self, fields):
        """
            聯絡人建立user 預設門戶使用者
        """
        res = super().default_get(fields)
        if self.env.context.get('partner_portal'):
            res['groups_id'] = [(6, 0, [self.env.ref('base.group_portal').id])]
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.env.context.get('partner_portal'):
                partner_id = self.env.context.get('existing_partner_id')
                if partner_id:
                    vals['partner_id'] = partner_id
                    if 'email' not in vals or not vals['email']:
                        #如果不加這段 初次連接使用者&聯絡人 聯絡人email 會被清空
                        vals['email'] = self.env.context.get('default_email') or self.env['res.partner'].browse(partner_id).email

        return super(ResUsers, self.with_context(from_user_create=True)).create(
            vals_list
        )


class GroupsView(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _update_user_groups_view(self):
        """Modify base.user_groups_view:
        - Internal user: keep standard access rights area
        - Portal user: only show custom front groups category
        - Public user: hide access rights area
        """
        self = self.with_context(lang=None)

        view = self.env.ref('base.user_groups_view', raise_if_not_found=False)
        if not (view and view._name == 'ir.ui.view'):
            return

        if self._context.get('install_filename') or self._context.get(MODULE_UNINSTALL_FLAG):
            xml = E.field(name="groups_id", position="after")
        else:
            group_no_one = view.env.ref('base.group_no_one')
            group_employee = view.env.ref('base.group_user')
            group_portal = view.env.ref('base.group_portal')
            front_category = self.env.ref('idx_ebs.module_category_front', raise_if_not_found=False)

            xml0 = []  # invisible duplicated fields for defaults/save
            xml1 = []  # user type
            xml2 = []  # warning
            xml3 = []  # internal selection categories
            xml4 = []  # internal boolean categories
            xml5 = []  # portal front groups only

            xml_by_category = {}
            xml1.append(E.separator(string='User Type', colspan="2", groups='base.group_no_one'))

            user_type_field_name = ''
            user_type_readonly = str({})
            sorted_tuples = sorted(self.get_groups_by_application(),
                                   key=lambda t: t[0].xml_id != 'base.module_category_user_type')
            for app, kind, gs, category_name in sorted_tuples:
                attrs = {}
                # hide groups in categories 'Hidden' and 'Extra' (except for group_no_one)
                if app.xml_id in self._get_hidden_extra_categories():
                    attrs['groups'] = 'base.group_no_one'

                # User Type
                if app.xml_id == 'base.module_category_user_type':
                    field_name = name_selection_groups(gs.ids)
                    xml0.append(E.field(name=field_name, invisible="1", on_change="1"))
                    user_type_field_name = field_name
                    user_type_readonly = f'{user_type_field_name} != {group_employee.id}'
                    attrs['widget'] = 'radio'
                    attrs['on_change'] = '1'
                    xml1.append(E.field(name=field_name, **attrs))
                    xml1.append(E.newline())
                    continue

                is_front_category = bool(front_category and app.id == front_category.id)

                # ---------------------------
                # Portal 專用：只顯示前台群組權限 category
                # ---------------------------
                if is_front_category:
                    portal_attrs = {}
                    if kind == 'selection':
                        field_name = name_selection_groups(gs.ids)
                        portal_attrs['on_change'] = '1'
                        xml5.append(E.field(name=field_name, **portal_attrs))
                        xml5.append(E.newline())

                        if attrs.get('groups') == 'base.group_no_one':
                            xml0.append(E.field(
                                name=field_name,
                                **dict(portal_attrs, invisible="1", groups='!base.group_no_one')
                            ))
                    else:
                        left_group, right_group = [], []
                        group_count = 0
                        for g in gs:
                            field_name = name_boolean_group(g.id)
                            dest_group = left_group if group_count % 2 == 0 else right_group
                            if g == group_no_one:
                                dest_group.append(E.field(name=field_name, invisible="1"))
                            else:
                                dest_group.append(E.field(name=field_name))
                            xml0.append(E.field(
                                name=field_name,
                                **dict(portal_attrs, invisible="1", groups='!base.group_no_one')
                            ))
                            group_count += 1
                        xml5.append(E.group(*left_group))
                        xml5.append(E.group(*right_group))
                    continue

                # ---------------------------
                # Internal 專用：其餘所有標準 category
                # ---------------------------
                if kind == 'selection':
                    field_name = name_selection_groups(gs.ids)
                    attrs['readonly'] = user_type_readonly
                    attrs['on_change'] = '1'
                    if category_name not in xml_by_category:
                        xml_by_category[category_name] = []
                        xml_by_category[category_name].append(E.newline())
                    xml_by_category[category_name].append(E.field(name=field_name, **attrs))
                    xml_by_category[category_name].append(E.newline())

                    if attrs.get('groups') == 'base.group_no_one':
                        xml0.append(E.field(
                            name=field_name,
                            **dict(attrs, invisible="1", groups='!base.group_no_one')
                        ))
                else:
                    app_name = app.name or 'Other'
                    xml4.append(E.separator(string=app_name, **attrs))
                    left_group, right_group = [], []
                    attrs['readonly'] = user_type_readonly
                    group_count = 0
                    for g in gs:
                        field_name = name_boolean_group(g.id)
                        dest_group = left_group if group_count % 2 == 0 else right_group
                        if g == group_no_one:
                            dest_group.append(E.field(name=field_name, invisible="1", **attrs))
                        else:
                            dest_group.append(E.field(name=field_name, **attrs))
                        xml0.append(E.field(
                            name=field_name,
                            **dict(attrs, invisible="1", groups='!base.group_no_one')
                        ))
                        group_count += 1
                    xml4.append(E.group(*left_group))
                    xml4.append(E.group(*right_group))

            xml4.append({'class': "o_label_nowrap"})

            internal_invisible = f'{user_type_field_name} != {group_employee.id}' if user_type_field_name else None
            portal_invisible = f'{user_type_field_name} != {group_portal.id}' if user_type_field_name else None

            for xml_cat in sorted(xml_by_category.keys(), key=lambda it: it[0]):
                master_category_name = xml_cat[1]
                xml3.append(E.group(*(xml_by_category[xml_cat]), string=master_category_name))

            field_name = 'user_group_warning'
            user_group_warning_xml = E.div({
                'class': "alert alert-warning",
                'role': "alert",
                'colspan': "2",
                'invisible': f'not {field_name}',
            })
            user_group_warning_xml.append(E.label({
                'for': field_name,
                'string': "Access Rights Mismatch",
                'class': "text text-warning fw-bold",
            }))
            user_group_warning_xml.append(E.field(name=field_name))
            xml2.append(user_group_warning_xml)

            xml = E.field(
                *xml0,
                E.group(*xml1, groups="base.group_no_one"),

                # Internal User 區塊
                E.group(*xml2, invisible=internal_invisible),
                E.group(*xml3, invisible=internal_invisible),
                E.group(*xml4, invisible=internal_invisible, groups="base.group_no_one"),

                # Portal 專用前台群組區塊
                E.group(
                    E.separator(string='前台群組權限', colspan="2"),
                    *xml5,
                    invisible=portal_invisible
                ),

                name="groups_id",
                position="replace"
            )
            xml.addprevious(etree.Comment("GENERATED AUTOMATICALLY BY GROUPS"))

        xml_content = etree.tostring(xml, pretty_print=True, encoding="unicode")
        if xml_content != view.arch:
            new_context = dict(view._context)
            new_context.pop('install_filename', None)
            new_context['lang'] = None
            view.with_context(new_context).write({'arch': xml_content})