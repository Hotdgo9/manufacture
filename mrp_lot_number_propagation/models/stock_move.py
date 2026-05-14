# Copyright 2022 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    propagate_lot_number = fields.Boolean(
        default=False,
        readonly=True,
    )

    def _action_assign(self, force_qty=False):
        res = super()._action_assign(force_qty=force_qty)
        self._ensure_production_propagating_finished_lot()
        return res

    def _ensure_production_propagating_finished_lot(self):
        # In case a lot propagating component is scrapped or unreserved after MOs were
        #  split through the mass produce wizard, the finished lot will still match
        #  the removed propagating component, so we must remove the outdated finished
        #  lot
        for move in self:
            finished_lot = move.raw_material_production_id.lot_producing_ids[:1]
            if (
                move.propagate_lot_number
                and finished_lot
                and len(move.move_line_ids) == 1
                and move.move_line_ids.lot_id.name != finished_lot.name
            ):
                # Pass lot_propagation context so the mrp.production.write
                # guard permits this internal clear; this is the propagation
                # logic itself, not an external user action.
                move.raw_material_production_id.with_context(
                    lot_propagation=True
                ).lot_producing_ids = [fields.Command.clear()]
                if not finished_lot.quant_ids:
                    finished_lot.unlink()
