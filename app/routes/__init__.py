def register_routes(app):
    """Register all route blueprints with the Flask app.

    Add your blueprints here. Example:
        from app.routes.products import products_bp
        app.register_blueprint(products_bp)
    """
    from app.routes.shortener import shortener_bp
    from app.routes.metrics import metrics_bp

    app.register_blueprint(shortener_bp)
    app.register_blueprint(metrics_bp)
