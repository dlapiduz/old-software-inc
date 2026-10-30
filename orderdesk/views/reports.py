from datetime import date

from flask import Blueprint, Response, render_template, request
from flask.ext.login import login_required

from orderdesk import csvexport, reports
from orderdesk.models import ORDER_STATUSES, Customer, Order
from orderdesk.utils import parse_date

bp = Blueprint('reports', __name__)


@bp.route('/reports/sales')
@login_required
def sales():
    today = date.today()
    start = parse_date(request.args.get('start')) or today.replace(day=1)
    end = parse_date(request.args.get('end')) or today
    summary = reports.sales_summary(start, end)
    top = reports.top_products(start, end)
    return render_template('reports/sales.html', summary=summary, top=top,
                           start=start, end=end)


def _csv_response(data, name):
    filename = '%s-%s.csv' % (name, date.today().isoformat())
    return Response(data, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=%s' % filename})


@bp.route('/reports/orders.csv')
@login_required
def export_orders():
    query = Order.query
    status = request.args.get('status')
    if status in ORDER_STATUSES:
        query = query.filter_by(status=status)
    return _csv_response(csvexport.export_orders(query.order_by(Order.id).all()), 'orders')


@bp.route('/reports/customers.csv')
@login_required
def export_customers():
    customers = Customer.query.order_by(Customer.account_number).all()
    return _csv_response(csvexport.export_customers(customers), 'customers')
