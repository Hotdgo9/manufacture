# Copyright 2025 Camptocamp SA
# Copyright 2026 Hotdgo9 (19.0 migration)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo import api, exceptions, fields, models


class MrpProductionSerials(models.TransientModel):
    _inherit = "mrp.production.serials"

    is_lot_number_propagated = fields.Boolean(
        related="production_id.is_lot_number_propagated"
    )
    lot_number_propagation_alert_msg = fields.Char(
        compute="_compute_lot_number_propagation_alert_msg"
    )

    @api.depends("is_lot_number_propagated")
    def _compute_lot_number_propagation_alert_msg(self):
        for wiz in self:
            msg = ""
            if wiz.is_lot_number_propagated:
                propagated_component = (
                    wiz.production_id._get_propagating_component_move().product_id
                )
                msg = self.env._(
                    "Lot number must be the same between finished product %(finished)s and component %(component)s",
                    finished=wiz.production_id.product_id.display_name,
                    component=propagated_component.display_name,
                )
            wiz.lot_number_propagation_alert_msg = msg

    def _parse_serial_numbers(self):
        self._check_propagated_lot_number()
        return super(
            MrpProductionSerials,
            self.with_context(lot_propagation=True),
        )._parse_serial_numbers()

    def action_apply(self):
        # Propagate lot_propagation context into the upstream action so the
        # mrp.production.write() guard in this module permits the legitimate
        # lot_producing_ids assignment performed by the parent action.
        return super(
            MrpProductionSerials,
            self.with_context(lot_propagation=True),
        ).action_apply()

    def action_split_and_assign_serials(self):
        # Same context propagation as action_apply: upstream writes
        # lot_producing_ids on each split MO and our write guard would
        # otherwise reject those writes for propagating productions.
        return super(
            MrpProductionSerials,
            self.with_context(lot_propagation=True),
        ).action_split_and_assign_serials()

    def _check_propagated_lot_number(self):
        if not self.is_lot_number_propagated:
            return
        propagating_move = self.production_id._get_propagating_component_move()
        propagating_lot_names = set(
            propagating_move.move_line_ids.lot_id.mapped("name")
        )
        if not propagating_lot_names:
            # Component lots not yet reserved — defer to upstream validation.
            # The mass-produce flow guards this separately in
            # mrp.production.serials.propagate._batch_produce.
            return
        supplied = [
            s.strip()
            for s in (self.serial_numbers or "").split("\n")
            if s.strip()
        ]
        unauthorized = [s for s in supplied if s not in propagating_lot_names]
        if unauthorized:
            raise exceptions.UserError(
                self.env._(
                    "As the product being produced is set to propagate lot number from component %(component)s, please make sure you define the same lot number between finished product and propagating component.",
                    component=propagating_move.product_id.display_name,
                )
            )
