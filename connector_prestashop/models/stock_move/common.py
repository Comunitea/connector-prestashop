# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.addons.component.core import Component


class StockLocation(models.Model):
    _inherit = 'stock.location'

    prestashop_synchronized = fields.Boolean(
        string='Sync with PrestaShop',
        help='Check this option to synchronize this location with PrestaShop')

    @api.model
    def get_prestashop_stock_locations(self):
        prestashop_locations = self.search([
            ('prestashop_synchronized', '=', True),
            ('usage', '=', 'internal'),
        ])
        return prestashop_locations


# class StockQuant(models.Model):
#     _inherit = 'stock.quant'

#     @api.model
#     def create(self, vals):
#         location_obj = self.env['stock.location']
#         ps_locations = location_obj.get_prestashop_stock_locations()
#         quant = super(StockQuant, self).create(vals)
#         if quant.location_id in ps_locations:
#             quant.invalidate_cache()
#             quant.product_id.update_prestashop_qty()
#         return quant

#     @api.multi
#     def write(self, vals):
#         location_obj = self.env['stock.location']
#         ps_locations = location_obj.get_prestashop_stock_locations()
#         for quant in self:
#             location = quant.location_id
#             super(StockQuant, self).write(vals)
#             if location in ps_locations or ('location_id' in vals and quant.location_id in ps_locations):
#                 quant.invalidate_cache()
#                 quant.product_id.update_prestashop_qty()
#         return True

#     @api.multi
#     def unlink(self):
#         ps_locations = self.env['stock.location'].\
#             get_prestashop_stock_locations()
#         self.filtered(lambda x: x.location_id in ps_locations).mapped(
#             'product_id').update_prestashop_qty()
#         return super(StockQuant, self).unlink()


class PrestashopStockPickingListener(Component):
    _name = 'prestashop.stock.picking.listener'
    _inherit = 'base.event.listener'
    _apply_on = ['stock.picking']

    def on_tracking_number_added(self, record):
        for binding in record.sale_id.prestashop_bind_ids:
            binding.with_delay().export_tracking_number()


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.multi
    def write(self, vals):
        stock_change_keys = ['state', 'product_uom_qty', 'location_id', 'location_dest_id']
        recompute = False
        for stock_field in stock_change_keys:
            if vals.get(stock_field):
                recompute = True
                break
        if recompute and not self._context.get('no_export_stock'):
            location_obj = self.env['stock.location']
            ps_locations_ids = location_obj.get_prestashop_stock_locations()._ids
            for move in self:
                locations = [move.location_id.id, move.location_dest_id.id]
            if vals.get('location_id'):
                locations.append(vals['location_id'])
            if vals.get('location_dest_id'):
                locations.append(vals['location_dest_id'])
            res = super(StockMove, self).write(vals)
            for move in self:
                if any([True for x in locations if x in ps_locations_ids]):
                    move.product_id.invalidate_cache()
                    move.product_id.update_prestashop_qty()
        else:
            res = super(StockMove, self).write(vals)
        return res


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    def post_inventory(self):
        res = super(StockInventory, self.with_context(no_export_stock=True)).post_inventory()
        for product in self.mapped('move_ids.product_id'):
            product.invalidate_cache()
            product.update_prestashop_qty()
        return res
