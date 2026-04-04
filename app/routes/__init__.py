def register_routes(app):
    """Register all route blueprints with the Flask app.

    Add your blueprints here. Example:
        from app.routes.products import products_bp
        app.register_blueprint(products_bp)
    """
    from app.routes.events import events_bp
    from app.routes.shortener import shortener_bp
    from app.routes.urls import urls_bp
    from app.routes.users import users_bp

    app.register_api(shortener_bp)
    app.register_api(users_bp)
    app.register_api(urls_bp)
    app.register_api(events_bp)
