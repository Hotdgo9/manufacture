# Copyright 2025 Camptocamp SA
# Copyright 2026 Hotdgo9 (19.0 migration)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models
from odoo.exceptions import UserError


class MrpProductionSerialsPropagate(models.TransientModel):
    _name = "mrp.production.serials.propagate"
    _description = "Batch production with lot number propagation"

    production_ids = fields.Many2many("mrp.production", readonly=True)

    def action_prepare(self):
        return self._batch_produce(mark_done=False)

    def action_done(self):
        return self._batch_produce(mark_done=True)

    def _batch_produce(self, mark_done=False):
        self.ensure_one()
        for production in self.production_ids:
            propagating_move = production._get_propagating_component_move()
            lot_names = [
                ml.lot_id.name
                for ml in propagating_move.move_line_ids
                if ml.lot_id
            ]
            if not lot_names:
                raise UserError(
                    self.env._(
                        "Cannot mass produce without any propagating component line having serial number defined."
                    )
                )
            wizard = (
                self.env["mrp.production.serials"]
                .with_context(
                    default_production_id=production.id,
                    lot_propagation=True,
                )
                .create({})
            )
            wizard.serial_numbers = "\n".join(lot_names)
            wizard.action_split_and_assign_serials()
            if mark_done:
                # After split, each child MO has exactly one serial in
                # lot_producing_ids. Locate the resulting MOs and mark the
                # propagating ones done. In Odoo 19, procurement_group_id was
                # replaced by production_group_id (a new mrp.production.group
                # intermediate). production_group_id.production_ids contains
                # the parent MO and its split siblings. Manually-created MOs
                # without a group fall back to the parent itself.
                child_mos = (
                    production.production_group_id.production_ids or production
                )
                child_mos.filtered(
                    lambda mo: mo.is_lot_number_propagated and mo.state != "done"
                ).with_context(skip_consumption=True).button_mark_done()
        return True
