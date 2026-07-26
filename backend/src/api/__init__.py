from api.analysis_controller import (
    AnalysisStartController,
    AnalysisLogsController,
    AnalysisStatusController,
    AnalysisListController,
    AnalysisDetectController,
    VLMModelsController,
)
from api.database_controller import (
    DatabaseUploadController,
    DatabaseDownloadController,
)
from api.events_controller import EventsDetectController
from api.schema_controller import (
    SchemaController,
    EventTypesController,
)

ROUTES = {
    '/analysis/start': AnalysisStartController(),
    '/analysis/list': AnalysisListController(),
    '/analysis/{analysis_id}/logs': AnalysisLogsController(),
    '/analysis/{analysis_id}/status': AnalysisStatusController(),
    '/analysis/{analysis_id}/detect': AnalysisDetectController(),
    '/vlm/models': VLMModelsController(),
    '/db/upload': DatabaseUploadController(),
    '/db/download': DatabaseDownloadController(),
    '/events/detect': EventsDetectController(),
    '/schema': SchemaController(),
    '/events/types': EventTypesController(),
}
