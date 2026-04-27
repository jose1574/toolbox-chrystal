from flask import Flask, render_template, redirect, url_for

from flask_login import login_required

from products_label import label_bp 

from app.models import (
    ProductsCode
)

@label_bp.route('/')
@login_required
def products_label():
    return render_template('products_label/index.html')