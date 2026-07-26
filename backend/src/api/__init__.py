from api.analysis_controller import (
    AnalysisStartController,
    AnalysisLogsController,
    AnalysisStatusController,
    AnalysisListController,
    AnalysisDetectController,
    AnalysisStopController,
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
from service.impl.analysis_service_impl import AnalysisServiceImpl

_analysis_service = AnalysisServiceImpl()

ROUTES = {
    '/analysis/start': AnalysisStartController(_analysis_service),
    '/analysis/list': AnalysisListController(_analysis_service),
    '/analysis/{analysis_id}/logs': AnalysisLogsController(_analysis_service),
    '/analysis/{analysis_id}/status': AnalysisStatusController(_analysis_service),
    '/analysis/{analysis_id}/detect': AnalysisDetectController(_analysis_service),
    '/analysis/{analysis_id}/stop': AnalysisStopController(_analysis_service),
    '/vlm/models': VLMModelsController(),
    '/db/upload': DatabaseUploadController(),
    '/db/download': DatabaseDownloadController(),
    '/events/detect': EventsDetectController(),
    '/schema': SchemaController(),
    '/events/types': EventTypesController(),
}
