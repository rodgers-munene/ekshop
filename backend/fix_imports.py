with open(r'D:\EKSHOP-STORE\ekshop\backend\app\routers\delivery.py', 'r') as f:
    content = f.read()

old_import = '''from app.schemas.delivery import (
    AgentLoginRequest, AgentTokenResponse,
    AgentStatusUpdate, AgentLocationUpdate,
    DeliveryAgentCreate, DeliveryAgentRead, DeliveryAgentListResponse,
    DeliveryIssueCreate, DeliveryIssueRead,
    DeliveryRead, DeliveryStatusUpdate,
    DeliveryRateRead, DeliveryRateUpdate,
    DeliverySimulationRow, DeliverySimulationResponse,
    RouteOptimizationRequest, RouteOptimizationResponse, RouteOptimizationStop,
    KYCDetailRead, KYCSubmitRequest, KYCReviewRequest,
    KYCAgentRead, KYCAgentListResponse,
    OfferRead, OfferListResponse, PingDispatchResponse,
    LedgerEntryRead, LedgerListResponse, WalletTransactionRequest,
    PricingRuleRead, PricingRuleListResponse, PricingRuleUpsert,
    MeteredQuoteRequest, MeteredQuoteResponse,
    DeliveryBatchRead, DeliveryBatchCreate, DeliveryBatchAssign,
    DeliveryBatchStatusUpdate, DeliveryBatchStatus,
    SafetyAlertRead, SafetyAlertCreate, SafetyAlertAcknowledge,
    EmergencyContactRead, EmergencyContactCreate, EmergencyContactUpdate,
    TripShareRead, TripShareCreate,
    DeliveryTrackingRead, AgentLocationRead,
    GPSFraudAlertRead, GPSFraudAlertListResponse, GPSFraudAlertReview,
    DeliveryStopCreate, DeliveryStopUpdate, DeliveryStopRead, DeliveryStopListResponse,
)'''

new_import = '''from app.schemas.delivery import (
    AgentLoginRequest, AgentTokenResponse,
    AgentStatusUpdate, AgentLocationUpdate,
    DeliveryAgentCreate, DeliveryAgentRead, DeliveryAgentListResponse,
    DeliveryIssueCreate, DeliveryIssueRead,
    DeliveryRead, DeliveryStatusUpdate,
    DeliveryRateRead, DeliveryRateUpdate,
    DeliverySimulationRow, DeliverySimulationResponse,
    RouteOptimizationRequest, RouteOptimizationResponse, RouteOptimizationStop,
    KYCDetailRead, KYCSubmitRequest, KYCReviewRequest,
    KYCAgentRead, KYCAgentListResponse,
    OfferRead, OfferListResponse, PingDispatchResponse,
    LedgerEntryRead, LedgerListResponse, WalletTransactionRequest,
    PricingRuleRead, PricingRuleListResponse, PricingRuleUpsert,
    MeteredQuoteRequest, MeteredQuoteResponse,
    DeliveryBatchRead, DeliveryBatchCreate, DeliveryBatchAssign,
    DeliveryBatchStatusUpdate, DeliveryBatchStatus,
    SafetyAlertRead, SafetyAlertCreate, SafetyAlertAcknowledge,
    EmergencyContactRead, EmergencyContactCreate, EmergencyContactUpdate,
    TripShareRead, TripShareCreate,
    DeliveryTrackingRead, AgentLocationRead,
    GPSFraudAlertRead, GPSFraudAlertListResponse, GPSFraudAlertReview,
    DeliveryStopCreate, DeliveryStopUpdate, DeliveryStopRead, DeliveryStopListResponse,
    VehicleRequirementRead, VehicleRequirementCreate, VehicleRequirementUpdate,
    VehicleRequirementListResponse, TemperatureRequirement,
)'''

if old_import in content:
    content = content.replace(old_import, new_import)
    with open(r'D:\EKSHOP-STORE\ekshop\backend\app\routers\delivery.py', 'w') as f:
        f.write(content)
    print('Successfully replaced')
else:
    print('Pattern not found')