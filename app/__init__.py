"""Application factory and package initialization for TECH5.

This module initializes the Flask application, establishes database tables,
and registers the Component A (Visualization & Recommendation) blueprint.
"""

import os
import sqlite3
from typing import Any

import flask

from app import config
from app.persistence import database
from app.visualization import routes as visualization_routes


def create_app(test_config: dict[str, Any] | None = None) -> flask.Flask:
    """Creates and configures an instance of the Flask application.

    Args:
        test_config: Optional configuration overrides for test execution.

    Returns:
        The configured Flask application object.
    """
    app = flask.Flask(
        __name__,
        template_folder=os.path.join(
            os.path.dirname(__file__), "visualization", "templates"
        ),
        static_folder=os.path.join(
            os.path.dirname(__file__), "visualization", "static"
        ),
    )

    app.config.from_object(config.Config)
    if test_config is not None:
        app.config.from_mapping(test_config)

    app.secret_key = app.config.get(
        "SECRET_KEY", "tech5-decision-support-secret-key-2026"
    )

    # Initialize relational database tables
    db_path = app.config.get("DATABASE_PATH")
    app.config["DATABASE_STARTUP_FAILED"] = False
    if db_path:
        try:
            db_mgr = database.DatabaseManager(db_path)
            database.db_manager = db_mgr
            db_mgr.initialize_schema()
        except (sqlite3.Error, OSError) as error:
            app.config["DATABASE_STARTUP_FAILED"] = True
            app.logger.error("Database initialization failed: %s", error)

    # Register Component A (Visualization & Recommendation) blueprint
    app.register_blueprint(visualization_routes.web_bp)

    @app.before_request
    def check_database_startup() -> tuple[str, int] | None:
        """Allow static assets and reject requests after database failure."""
        if (
            app.config["DATABASE_STARTUP_FAILED"]
            and flask.request.endpoint != "static"
        ):
            return flask.render_template(
                "database_error.html",
                title="Database unavailable",
                message=(
                    "The database could not be opened when the app started. "
                    "Check the file and restart the app."
                ),
            ), 503
        return None

    @app.errorhandler(sqlite3.DatabaseError)
    def database_failure(error: sqlite3.DatabaseError) -> tuple[str, int]:
        """Report unavailable database operations with HTTP 503."""
        app.logger.warning("Database operation failed: %s", error)
        return flask.render_template(
            "database_error.html",
            title="Database unavailable",
            message=(
                "The database could not be read or saved. Check whether it is "
                "locked, read-only, unavailable, or damaged, then try again."
            ),
        ), 503

    @app.errorhandler(database.InvalidDatabaseRecords)
    def invalid_saved_inputs(
        error: database.InvalidDatabaseRecords,
    ) -> tuple[str, int]:
        """Report invalid saved records without generating assignments."""
        return flask.render_template(
            "database_error.html",
            title="Invalid saved input records",
            message=(
                "Correct the records below before starting a run. No "
                "assignments were generated."
            ),
            errors=error.errors,
        ), 422

    return app
