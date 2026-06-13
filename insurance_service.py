from flask import Flask, request, jsonify
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

app = Flask(__name__)


@dataclass
class VehicleInfo:
    brand: str
    vehicle_age: int
    claim_count_last_year: int
    claim_free_years: int = 0
    seats: int = 5
    purchase_price: float = 150000.0
    displacement: float = 1.6
    third_party_limit: int = 1000000
    driver_insurance: bool = True
    passenger_insurance: bool = True
    driver_limit: int = 10000
    passenger_limit: int = 10000
    theft_insurance: bool = True


class CompulsoryInsuranceCalculator:
    BASE_PREMIUM_6_SEATS_BELOW = 950
    BASE_PREMIUM_6_SEATS_ABOVE = 1100

    CLAIM_FREE_FACTOR = {
        1: 0.9,
        2: 0.8,
        3: 0.7,
    }

    @classmethod
    def calculate(cls, seats: int, claim_count: int, claim_free_years: int = 0) -> Tuple[float, Dict]:
        base_premium = (
            cls.BASE_PREMIUM_6_SEATS_BELOW
            if seats <= 5
            else cls.BASE_PREMIUM_6_SEATS_ABOVE
        )

        if claim_count == 0 and claim_free_years > 0:
            tier = min(claim_free_years, 3)
            factor = cls.CLAIM_FREE_FACTOR[tier]
        elif claim_count == 0:
            factor = 1.0
        elif claim_count == 1:
            factor = 1.0
        else:
            factor = 1.0 + 0.1 * claim_count
            factor = min(factor, 2.0)

        premium = round(base_premium * factor, 2)

        tax = cls._calculate_vehicle_and_vessel_tax()
        total = round(premium + tax, 2)

        detail = {
            "base_premium": base_premium,
            "factor": factor,
            "claim_count_last_year": claim_count,
            "consecutive_claim_free_years": claim_free_years,
            "premium": premium,
            "vehicle_and_vessel_tax": tax,
            "total": total,
        }
        return total, detail

    @classmethod
    def _calculate_vehicle_and_vessel_tax(cls) -> float:
        return 420.0


class CommercialInsuranceCalculator:
    BRAND_FACTOR = {
        "default": 1.0,
        "大众": 1.0,
        "丰田": 0.95,
        "本田": 0.95,
        "奔驰": 1.2,
        "宝马": 1.2,
        "奥迪": 1.15,
        "比亚迪": 1.0,
        "特斯拉": 1.25,
        "保时捷": 1.5,
    }

    AGE_FACTOR_TABLE = [
        (0, 1.0),
        (1, 1.0),
        (3, 1.05),
        (5, 1.1),
        (8, 1.15),
        (10, 1.2),
    ]

    NCD_CLAIM_FREE_FACTOR = {
        1: 0.7,
        2: 0.6,
        3: 0.5,
    }

    NCD_CLAIM_FACTOR_TABLE = [
        (1, 1.0),
        (2, 1.25),
        (3, 1.5),
        (4, 1.75),
    ]

    @classmethod
    def calculate(cls, vehicle: VehicleInfo) -> Tuple[float, Dict]:
        details = {}

        vehicle_loss_premium, vl_detail = cls._calculate_vehicle_loss(vehicle)
        details["vehicle_loss_insurance"] = vl_detail

        third_party_premium, tp_detail = cls._calculate_third_party(vehicle)
        details["third_party_insurance"] = tp_detail

        driver_premium = 0.0
        passenger_premium = 0.0
        if vehicle.driver_insurance:
            driver_premium, d_detail = cls._calculate_driver_insurance(vehicle)
            details["driver_insurance"] = d_detail
        if vehicle.passenger_insurance:
            passenger_premium, p_detail = cls._calculate_passenger_insurance(vehicle)
            details["passenger_insurance"] = p_detail

        theft_premium = 0.0
        if vehicle.theft_insurance:
            theft_premium, t_detail = cls._calculate_theft_insurance(vehicle)
            details["theft_insurance"] = t_detail

        subtotal = round(
            vehicle_loss_premium
            + third_party_premium
            + driver_premium
            + passenger_premium
            + theft_premium,
            2,
        )

        no_claim_discount = cls._get_ncd_factor(
            vehicle.claim_count_last_year, vehicle.claim_free_years
        )
        brand_factor = cls.BRAND_FACTOR.get(vehicle.brand, cls.BRAND_FACTOR["default"])
        age_factor = cls._get_age_factor(vehicle.vehicle_age)

        adjusted = round(
            subtotal * no_claim_discount * brand_factor * age_factor, 2
        )

        total = round(adjusted, 2)

        summary = {
            "subtotal_before_adjustment": subtotal,
            "no_claim_discount_factor": no_claim_discount,
            "consecutive_claim_free_years": vehicle.claim_free_years,
            "brand_factor": brand_factor,
            "age_factor": age_factor,
            "total": total,
            "details": details,
        }
        return total, summary

    @classmethod
    def _calculate_vehicle_loss(cls, v: VehicleInfo) -> Tuple[float, Dict]:
        rate = 0.015
        premium = round(v.purchase_price * rate, 2)
        deductible = round(premium * 0.2, 2)
        return premium, {
            "basis": v.purchase_price,
            "rate": rate,
            "premium": premium,
            "deductible": deductible,
        }

    @classmethod
    def _calculate_third_party(cls, v: VehicleInfo) -> Tuple[float, Dict]:
        limit_table = {
            50000: 611,
            100000: 899,
            200000: 1191,
            300000: 1396,
            500000: 1781,
            1000000: 2242,
            2000000: 3181,
            3000000: 4081,
            5000000: 5745,
        }
        best_limit = min(limit_table.keys(), key=lambda x: abs(x - v.third_party_limit))
        premium = float(limit_table.get(best_limit, 2242))
        return premium, {
            "coverage_limit": best_limit,
            "premium": premium,
        }

    @classmethod
    def _calculate_driver_insurance(cls, v: VehicleInfo) -> Tuple[float, Dict]:
        rate = 0.0042
        premium = round(v.driver_limit * rate, 2)
        return premium, {
            "coverage_limit": v.driver_limit,
            "rate": rate,
            "premium": premium,
        }

    @classmethod
    def _calculate_passenger_insurance(cls, v: VehicleInfo) -> Tuple[float, Dict]:
        rate = 0.0027
        passenger_count = max(v.seats - 1, 1)
        premium = round(v.passenger_limit * rate * passenger_count, 2)
        return premium, {
            "passenger_count": passenger_count,
            "coverage_limit_per_person": v.passenger_limit,
            "rate": rate,
            "premium": premium,
        }

    @classmethod
    def _calculate_theft_insurance(cls, v: VehicleInfo) -> Tuple[float, Dict]:
        rate = 0.005
        depreciation = max(1.0 - v.vehicle_age * 0.06, 0.2)
        insured_value = round(v.purchase_price * depreciation, 2)
        premium = round(insured_value * rate, 2)
        return premium, {
            "original_price": v.purchase_price,
            "depreciation_rate": round(1 - depreciation, 4),
            "insured_value": insured_value,
            "rate": rate,
            "premium": premium,
        }

    @classmethod
    def _get_age_factor(cls, age: int) -> float:
        factor = 1.3
        for limit, f in cls.AGE_FACTOR_TABLE:
            if age <= limit:
                factor = f
                break
        return factor

    @classmethod
    def _get_ncd_factor(cls, claim_count: int, claim_free_years: int) -> float:
        if claim_count == 0:
            if claim_free_years >= 3:
                return cls.NCD_CLAIM_FREE_FACTOR[3]
            elif claim_free_years == 2:
                return cls.NCD_CLAIM_FREE_FACTOR[2]
            elif claim_free_years == 1:
                return cls.NCD_CLAIM_FREE_FACTOR[1]
            else:
                return 1.0

        factor = 2.0
        for limit, f in cls.NCD_CLAIM_FACTOR_TABLE:
            if claim_count <= limit:
                factor = f
                break
        return factor


@dataclass
class InsuranceCompany:
    code: str
    name: str
    slogan: str
    base_discount: float
    ncd_strictness: float
    age_sensitivity: float
    brand_preference: Dict[str, float]
    new_car_bonus: float
    high_claim_surcharge: float
    value_added_services: List[str]
    rating: float
    complaint_ratio: float


class CompanyRegistry:
    COMPANIES: Dict[str, InsuranceCompany] = {
        "PICC": InsuranceCompany(
            code="PICC",
            name="中国人保",
            slogan="服务网点最多，理赔响应快",
            base_discount=0.95,
            ncd_strictness=1.05,
            age_sensitivity=1.0,
            brand_preference={"大众": 0.95, "丰田": 0.95, "本田": 0.95, "别克": 0.95},
            new_car_bonus=0.98,
            high_claim_surcharge=1.08,
            value_added_services=["50公里免费道路救援", "全国通赔", "现场定损"],
            rating=4.7,
            complaint_ratio=0.8,
        ),
        "PINGAN": InsuranceCompany(
            code="PINGAN",
            name="平安车险",
            slogan="科技赋能，先赔付后修车",
            base_discount=0.92,
            ncd_strictness=0.98,
            age_sensitivity=0.95,
            brand_preference={"特斯拉": 0.9, "比亚迪": 0.9, "蔚来": 0.9, "小鹏": 0.9},
            new_car_bonus=0.95,
            high_claim_surcharge=1.1,
            value_added_services=["百公里免费救援", "免费代步车3天", "AI智能定损", "车主贷绿色通道"],
            rating=4.8,
            complaint_ratio=0.6,
        ),
        "CPIC": InsuranceCompany(
            code="CPIC",
            name="太平洋保险",
            slogan="坐享其成，省心服务",
            base_discount=0.93,
            ncd_strictness=1.0,
            age_sensitivity=1.05,
            brand_preference={"奔驰": 0.98, "宝马": 0.98, "奥迪": 0.98},
            new_car_bonus=0.96,
            high_claim_surcharge=1.05,
            value_added_services=["50公里道路救援", "酒后代驾2次", "机场贵宾厅1次"],
            rating=4.6,
            complaint_ratio=0.9,
        ),
        "CHINALIFE": InsuranceCompany(
            code="CHINALIFE",
            name="中国人寿财险",
            slogan="相知多年，值得托付",
            base_discount=0.94,
            ncd_strictness=1.02,
            age_sensitivity=0.98,
            brand_preference={"default": 1.0},
            new_car_bonus=0.97,
            high_claim_surcharge=1.0,
            value_added_services=["道路救援", "代驾服务", "家政服务抵用券"],
            rating=4.5,
            complaint_ratio=1.0,
        ),
        "TAIPING": InsuranceCompany(
            code="TAIPING",
            name="太平保险",
            slogan="央企背景，稳健之选",
            base_discount=0.90,
            ncd_strictness=0.9,
            age_sensitivity=1.1,
            brand_preference={"default": 0.98},
            new_car_bonus=0.92,
            high_claim_surcharge=1.15,
            value_added_services=["30公里道路救援", "年检代办", "车辆美容折扣"],
            rating=4.4,
            complaint_ratio=1.1,
        ),
        "SUNSHINE": InsuranceCompany(
            code="SUNSHINE",
            name="阳光保险",
            slogan="性价比首选，闪赔快赔",
            base_discount=0.88,
            ncd_strictness=0.85,
            age_sensitivity=0.9,
            brand_preference={"default": 0.97, "五菱": 0.95, "长安": 0.95, "哈弗": 0.95},
            new_car_bonus=0.90,
            high_claim_surcharge=1.2,
            value_added_services=["闪赔服务(5000元以下24小时到账)", "道路救援", "违章查询提醒"],
            rating=4.3,
            complaint_ratio=1.3,
        ),
    }

    @classmethod
    def get_all(cls) -> List[InsuranceCompany]:
        return list(cls.COMPANIES.values())

    @classmethod
    def get(cls, code: str) -> Optional[InsuranceCompany]:
        return cls.COMPANIES.get(code)


class PriceComparisonEngine:
    @classmethod
    def quote_company(
        cls,
        company: InsuranceCompany,
        vehicle: VehicleInfo,
        compulsory_detail: Dict,
        commercial_detail: Dict,
        standard_total: float,
    ) -> Dict:
        compulsory = compulsory_detail["total"]
        commercial = commercial_detail["total"]

        brand_factor = company.brand_preference.get(
            vehicle.brand, company.brand_preference.get("default", 1.0)
        )

        ncd_factor_commercial = commercial_detail["no_claim_discount_factor"]
        if vehicle.claim_count_last_year == 0:
            ncd_adjustment = 1.0 - (1.0 - ncd_factor_commercial) * (1.0 + (1.0 - company.ncd_strictness))
        else:
            ncd_penalty_basis = ncd_factor_commercial - 1.0
            ncd_adjustment = 1.0 + ncd_penalty_basis * company.ncd_strictness

        if vehicle.vehicle_age <= 1:
            age_bonus = company.new_car_bonus
        else:
            if company.age_sensitivity >= 1.0:
                age_bonus = 1.0 + min((vehicle.vehicle_age - 1) * 0.005 * company.age_sensitivity, 0.1)
            else:
                age_bonus = 1.0 - min((vehicle.vehicle_age - 1) * 0.003 * (1.0 - company.age_sensitivity) * 10, 0.08)

        if vehicle.claim_count_last_year >= 3:
            claim_surcharge = company.high_claim_surcharge
        else:
            claim_surcharge = 1.0

        final_company_factor = round(
            company.base_discount
            * brand_factor
            * ncd_adjustment
            * age_bonus
            * claim_surcharge,
            4,
        )

        commercial_adjusted = round(commercial * final_company_factor, 2)
        total = round(compulsory + commercial_adjusted, 2)

        savings = round(standard_total - total, 2)

        return {
            "company_code": company.code,
            "company_name": company.name,
            "slogan": company.slogan,
            "rating": company.rating,
            "complaint_ratio": company.complaint_ratio,
            "value_added_services": company.value_added_services,
            "breakdown": {
                "compulsory_insurance_total": compulsory,
                "commercial_insurance_standard": commercial,
                "commercial_insurance_adjusted": commercial_adjusted,
                "grand_total": total,
            },
            "factors_applied": {
                "base_discount": company.base_discount,
                "brand_preference": brand_factor,
                "ncd_adjustment": round(ncd_adjustment, 4),
                "age_bonus": round(age_bonus, 4),
                "high_claim_surcharge": claim_surcharge,
                "final_combined_factor": final_company_factor,
            },
            "standard_price_comparison": {
                "standard_total": standard_total,
                "savings": savings,
                "savings_percent": round(savings / standard_total * 100, 2) if standard_total > 0 else 0.0,
            },
        }

    @classmethod
    def compare_all(
        cls,
        vehicle: VehicleInfo,
        compulsory_detail: Dict,
        commercial_detail: Dict,
        preferred_companies: Optional[List[str]] = None,
    ) -> Dict:
        standard_total = round(compulsory_detail["total"] + commercial_detail["total"], 2)

        companies = CompanyRegistry.get_all()
        if preferred_companies:
            companies = [
                c for c in companies if c.code in preferred_companies
            ]

        quotes = [
            cls.quote_company(c, vehicle, compulsory_detail, commercial_detail, standard_total)
            for c in companies
        ]

        quotes.sort(key=lambda q: q["breakdown"]["grand_total"])

        cheapest = quotes[0] if quotes else None
        highest_rated = max(quotes, key=lambda q: q["rating"]) if quotes else None
        best_service = max(quotes, key=lambda q: -q["complaint_ratio"]) if quotes else None

        return {
            "standard_total": standard_total,
            "quote_count": len(quotes),
            "recommendations": {
                "cheapest": cheapest["company_code"] if cheapest else None,
                "highest_rated": highest_rated["company_code"] if highest_rated else None,
                "best_service": best_service["company_code"] if best_service else None,
            },
            "price_range": {
                "lowest": cheapest["breakdown"]["grand_total"] if cheapest else 0.0,
                "highest": quotes[-1]["breakdown"]["grand_total"] if quotes else 0.0,
                "difference": round(
                    (quotes[-1]["breakdown"]["grand_total"] - cheapest["breakdown"]["grand_total"]), 2
                ) if quotes and len(quotes) >= 2 else 0.0,
            },
            "quotes": quotes,
        }


def calculate_total_premium(vehicle: VehicleInfo, preferred_companies: Optional[List[str]] = None) -> Dict:
    compulsory_total, compulsory_detail = CompulsoryInsuranceCalculator.calculate(
        vehicle.seats, vehicle.claim_count_last_year, vehicle.claim_free_years
    )
    commercial_total, commercial_detail = CommercialInsuranceCalculator.calculate(vehicle)

    grand_total = round(compulsory_total + commercial_total, 2)

    comparison = PriceComparisonEngine.compare_all(
        vehicle, compulsory_detail, commercial_detail, preferred_companies
    )

    return {
        "vehicle_info": {
            "brand": vehicle.brand,
            "vehicle_age": vehicle.vehicle_age,
            "claim_count_last_year": vehicle.claim_count_last_year,
            "consecutive_claim_free_years": vehicle.claim_free_years,
            "seats": vehicle.seats,
            "purchase_price": vehicle.purchase_price,
            "displacement": vehicle.displacement,
        },
        "compulsory_insurance": compulsory_detail,
        "commercial_insurance": commercial_detail,
        "grand_total_standard": grand_total,
        "price_comparison": comparison,
    }


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    try:
        data = request.get_json(force=True)

        required_fields = ["brand", "vehicle_age", "claim_count_last_year"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"缺少必填字段: {field}"}), 400

        vehicle = VehicleInfo(
            brand=str(data["brand"]),
            vehicle_age=int(data["vehicle_age"]),
            claim_count_last_year=int(data["claim_count_last_year"]),
            claim_free_years=int(data.get("claim_free_years", 0)),
            seats=int(data.get("seats", 5)),
            purchase_price=float(data.get("purchase_price", 150000)),
            displacement=float(data.get("displacement", 1.6)),
            third_party_limit=int(data.get("third_party_limit", 1000000)),
            driver_insurance=bool(data.get("driver_insurance", True)),
            passenger_insurance=bool(data.get("passenger_insurance", True)),
            driver_limit=int(data.get("driver_limit", 10000)),
            passenger_limit=int(data.get("passenger_limit", 10000)),
            theft_insurance=bool(data.get("theft_insurance", True)),
        )

        if vehicle.vehicle_age < 0:
            return jsonify({"error": "车龄不能为负数"}), 400
        if vehicle.claim_count_last_year < 0:
            return jsonify({"error": "出险次数不能为负数"}), 400
        if vehicle.claim_free_years < 0:
            return jsonify({"error": "连续无出险年数不能为负数"}), 400

        preferred_companies_raw = data.get("preferred_companies")
        preferred_companies = None
        if preferred_companies_raw:
            if isinstance(preferred_companies_raw, str):
                preferred_companies = [c.strip().upper() for c in preferred_companies_raw.split(",")]
            elif isinstance(preferred_companies_raw, list):
                preferred_companies = [str(c).strip().upper() for c in preferred_companies_raw]

            valid_codes = set(CompanyRegistry.COMPANIES.keys())
            invalid = [c for c in preferred_companies if c not in valid_codes]
            if invalid:
                return jsonify({"error": f"不支持的保险公司代码: {invalid}，可选: {sorted(valid_codes)}"}), 400

        result = calculate_total_premium(vehicle, preferred_companies)
        return jsonify({"success": True, "data": result})

    except ValueError as e:
        return jsonify({"error": f"参数格式错误: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "车险保费试算服务"})


@app.route("/api/companies", methods=["GET"])
def list_companies():
    companies = []
    for c in CompanyRegistry.get_all():
        companies.append({
            "code": c.code,
            "name": c.name,
            "slogan": c.slogan,
            "rating": c.rating,
            "complaint_ratio": c.complaint_ratio,
            "base_discount": c.base_discount,
            "value_added_services": c.value_added_services,
            "preferred_brands": [b for b in c.brand_preference.keys() if b != "default"],
        })
    return jsonify({"success": True, "count": len(companies), "companies": companies})


def demo():
    demo_cases = [
        VehicleInfo("丰田", 1, 0, claim_free_years=3, purchase_price=200000),
        VehicleInfo("大众", 3, 0, claim_free_years=1, purchase_price=150000),
        VehicleInfo("奔驰", 5, 1, claim_free_years=0, seats=7, purchase_price=500000),
        VehicleInfo("比亚迪", 0, 2, claim_free_years=0, purchase_price=180000, third_party_limit=2000000),
    ]

    print("=" * 90)
    print("车险保费试算服务 - 演示案例 (NCD修复 + 多公司比价)")
    print("=" * 90)

    for i, v in enumerate(demo_cases, 1):
        result = calculate_total_premium(v)
        print(f"\n=== 案例 {i}: {v.brand} | 车龄{v.vehicle_age}年 | 上年出险{v.claim_count_last_year}次 | 连续无出险{v.claim_free_years}年 ===")
        print(f"  交强险: {result['compulsory_insurance']['total']:.2f} 元  "
              f"(基础{result['compulsory_insurance']['base_premium']}×系数{result['compulsory_insurance']['factor']} + 车船税{result['compulsory_insurance']['vehicle_and_vessel_tax']})")
        ci = result["commercial_insurance"]
        print(f"  商业险(标准): {ci['total']:.2f} 元  (NCD:{ci['no_claim_discount_factor']} 品牌:{ci['brand_factor']} 车龄:{ci['age_factor']})")
        print(f"  标准合计: {result['grand_total_standard']:.2f} 元")

        pc = result["price_comparison"]
        print(f"\n  ┌────────────────────────────────────────── 保险公司比价 ({pc['quote_count']}家) ──────────────────────────────────────────┐")
        print(f"  │ {'排名':<3} {'公司':<10} {'总保费':<10} {'节省':<8} {'折扣':<6} {'综合系数':<8} {'评分':<5}  {'特色增值服务'}")
        print(f"  │{'-' * 108}│")

        rec = pc["recommendations"]
        tags_map = {}
        if rec["cheapest"]:
            tags_map.setdefault(rec["cheapest"], []).append("最省")
        if rec["highest_rated"]:
            tags_map.setdefault(rec["highest_rated"], []).append("高分")
        if rec["best_service"]:
            tags_map.setdefault(rec["best_service"], []).append("好评")

        for rank, q in enumerate(pc["quotes"], 1):
            tags = tags_map.get(q["company_code"], [])
            tag_str = "/".join(tags)
            name_display = q["company_name"]
            if tag_str:
                name_display += f"[{tag_str}]"
            service_short = "、".join(q["value_added_services"][:2])
            print(
                f"  │ {rank:<3} {name_display:<14} {q['breakdown']['grand_total']:>8.2f}  "
                f"{q['standard_price_comparison']['savings']:>+7.2f} "
                f"{q['standard_price_comparison']['savings_percent']:>+5.1f}% "
                f"{q['factors_applied']['final_combined_factor']:>7.4f}  "
                f"{q['rating']:>4.1f}★  {service_short}"
            )

        print(f"  └────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘")
        print(f"  推荐: 最便宜→{CompanyRegistry.get(rec['cheapest']).name if rec['cheapest'] else '-'}  |  "
              f"口碑→{CompanyRegistry.get(rec['highest_rated']).name if rec['highest_rated'] else '-'}  |  "
              f"服务→{CompanyRegistry.get(rec['best_service']).name if rec['best_service'] else '-'}")
        pr = pc["price_range"]
        print(f"  报价区间: {pr['lowest']:.2f} ~ {pr['highest']:.2f} 元 (差价 {pr['difference']:.2f} 元)")
    print("\n" + "=" * 90)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        print("启动车险保费试算服务 HTTP API...")
        print("接口: POST http://localhost:5000/api/calculate")
        app.run(host="0.0.0.0", port=5000, debug=False)
    else:
        demo()
