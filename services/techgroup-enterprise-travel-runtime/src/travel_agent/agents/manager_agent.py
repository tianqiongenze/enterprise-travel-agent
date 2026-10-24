"""Module contains agent implementations."""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ..models import RecommendationItem, TravelRecommendation, TravelRequest
from .llm import LlmRationaleDecorator

if TYPE_CHECKING:
    from ..recommendation.recommender import TravelRecommender


class ManagerAgent:
    def __init__(
        self,
        route_agent: "RouteMakingAgent",
        trip_agent: "TripPlannerAgent",
        food_agent: "FoodRecommendationAgent",
        event_agent: "LocalEventAgent",
        loyalty_agent: "LoyaltyGrowthAgent",
        weather_agent: "WeatherRiskAgent",
        ancillary_agent: "AncillaryRevenueAgent",
        visa_agent: "VisaComplianceAgent",
        concierge_agent: "ConciergeAgent",
        local_lifestyle_agent: "LocalLifestyleAgent",
        rationale_decorator: Optional[LlmRationaleDecorator] = None,
    ) -> None:
        self.route_agent = route_agent
        self.trip_agent = trip_agent
        self.food_agent = food_agent
        self.event_agent = event_agent
        self.loyalty_agent = loyalty_agent
        self.weather_agent = weather_agent
        self.ancillary_agent = ancillary_agent
        self.visa_agent = visa_agent
        self.concierge_agent = concierge_agent
        self.local_lifestyle_agent = local_lifestyle_agent
        self.rationale_decorator = rationale_decorator

    def execute(self, request: TravelRequest, weights: Dict[str, float]) -> TravelRecommendation:
        hotel_options, transport_options = self.route_agent.plan_routes(request, weights)
        itinerary = self.trip_agent.plan_trip(request, hotel_options, transport_options)
        food_pack = self.food_agent.recommend_food(request)
        event_pack = self.event_agent.recommend_events(request)
        growth_pack = self.loyalty_agent.build_growth_actions(request)
        weather_pack = self.weather_agent.build_risk_hints(request)
        ancillary_pack = self.ancillary_agent.build_upsell_actions(request)
        visa_pack = self.visa_agent.build_visa_guidance(request)
        concierge_pack = self.concierge_agent.build_concierge_actions(request)
        lifestyle_pack = self.local_lifestyle_agent.recommend_local_lifestyle(request)
        engagement_recommendations = food_pack + event_pack + lifestyle_pack + growth_pack + weather_pack + ancillary_pack + visa_pack + concierge_pack
        if self.rationale_decorator is not None:
            engagement_recommendations = self.rationale_decorator.enrich(
                {
                    "city": request.city,
                    "preferences": list(request.preferences),
                    "budget": request.budget,
                    "days": request.days,
                },
                engagement_recommendations,
            )
        return TravelRecommendation(
            hotel_options=hotel_options,
            transport_options=transport_options,
            itinerary=itinerary,
            engagement_recommendations=engagement_recommendations,
        )


class RouteMakingAgent:
    def __init__(self, recommender: "TravelRecommender") -> None:
        self.recommender = recommender

    def plan_routes(self, request: TravelRequest, weights: Dict[str, float]) -> Tuple[List[RecommendationItem], List[RecommendationItem]]:
        hotels = self.recommender.recommend_hotels(request, weights)
        transports = self.recommender.recommend_transports(request, weights)
        return hotels, transports


class TripPlannerAgent:
    def __init__(self, recommender: "TravelRecommender") -> None:
        self.recommender = recommender

    def plan_trip(
        self,
        request: TravelRequest,
        hotels: List[RecommendationItem],
        transports: List[RecommendationItem],
    ) -> List[Dict[str, str]]:
        return self.recommender.recommend_itinerary(request, hotels, transports)


class FoodRecommendationAgent:
    def __init__(self, recommender: "TravelRecommender") -> None:
        self.recommender = recommender

    def recommend_food(self, request: TravelRequest) -> List[Dict[str, str]]:
        rows = self.recommender.recommend_foods(request)
        return [
            {"type": "food", "title": str(row.get("name", "餐饮推荐")), "reason": "本地口碑与偏好匹配"}
            for row in rows
        ]


class LocalEventAgent:
    def __init__(self, recommender: "TravelRecommender") -> None:
        self.recommender = recommender

    def recommend_events(self, request: TravelRequest) -> List[Dict[str, str]]:
        rows = self.recommender.recommend_events(request)
        return [
            {"type": "event", "title": str(row.get("name", "活动推荐")), "reason": "旅程时段与城市活动匹配"}
            for row in rows
        ]


class LocalLifestyleAgent:
    def __init__(self, recommender: "TravelRecommender") -> None:
        self.recommender = recommender
        self._providers = [
            ("activity", self.recommender.recommend_activities, "本地玩法与偏好匹配，适合城市深度体验"),
            ("souvenir", self.recommender.recommend_souvenirs, "本地特色伴手礼，兼顾文化辨识度与复购价值"),
        ]

    def recommend_local_lifestyle(self, request: TravelRequest) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for item_type, fetcher, default_reason in self._providers:
            for entry in fetcher(request):
                rows.append(
                    {
                        "type": item_type,
                        "title": str(entry.get("name", "本地生活推荐")),
                        "reason": str(entry.get("reason", default_reason)),
                    }
                )
        return rows


class LoyaltyGrowthAgent:
    def build_growth_actions(self, request: TravelRequest) -> List[Dict[str, str]]:
        return [
            {
                "type": "growth",
                "title": f"{request.city} 连住权益包",
                "reason": "提升复购与停留时长，增强业务粘性",
            },
            {
                "type": "growth",
                "title": "会员积分与二次触达策略",
                "reason": "提升用户生命周期价值与复访率",
            },
        ]


class WeatherRiskAgent:
    def build_risk_hints(self, request: TravelRequest) -> List[Dict[str, str]]:
        if request.days >= 4:
            return [
                {
                    "type": "risk",
                    "title": f"{request.city} 长行程天气备选方案",
                    "reason": "多日行程受天气影响更大，建议预置室内替代点位",
                }
            ]
        return [
            {
                "type": "risk",
                "title": f"{request.city} 出行当天天气提醒",
                "reason": "短行程建议按小时天气动态微调交通与景点顺序",
            }
        ]


class AncillaryRevenueAgent:
    def build_upsell_actions(self, request: TravelRequest) -> List[Dict[str, str]]:
        tier = "家庭权益" if "family" in request.preferences else "舒适升级"
        return [
            {
                "type": "upsell",
                "title": f"{tier}增购包",
                "reason": "以低门槛增购提升客单价，同时不破坏主链路转化",
            }
        ]


class VisaComplianceAgent:
    def build_visa_guidance(self, request: TravelRequest) -> List[Dict[str, str]]:
        if "international" in request.preferences:
            return [
                {
                    "type": "compliance",
                    "title": "跨境签证与入境材料核验",
                    "reason": "国际行程优先校验签证/保险/入境政策，降低行程中断风险",
                }
            ]
        return []


class ConciergeAgent:
    def build_concierge_actions(self, request: TravelRequest) -> List[Dict[str, str]]:
        if request.membership_tier not in {"gold", "platinum"}:
            return []
        return [
            {
                "type": "concierge",
                "title": f"{request.city} 专属管家服务",
                "reason": "高等级会员可使用 7x24 行程改签与紧急服务协调",
            }
        ]


