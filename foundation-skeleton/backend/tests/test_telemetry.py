import importlib


def test_configure_telemetry_skips_exporters_in_test_env(monkeypatch):
    telemetry = importlib.import_module("app.core.telemetry")
    config = importlib.import_module("app.core.config")

    config.get_settings.cache_clear()

    class DummySettings:
        app_env = "test"
        otel_service_name = "foundation-backend"
        otel_exporter_otlp_endpoint = None

    calls = {"batch": 0, "provider": 0}

    monkeypatch.setattr(telemetry, "get_settings", lambda: DummySettings())

    def fake_batch_span_processor(*args, **kwargs):
        calls["batch"] += 1
        return object()

    def fake_set_tracer_provider(*args, **kwargs):
        calls["provider"] += 1

    monkeypatch.setattr(telemetry, "BatchSpanProcessor", fake_batch_span_processor)
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", fake_set_tracer_provider)

    telemetry.configure_telemetry()

    assert calls["batch"] == 0
    assert calls["provider"] == 0