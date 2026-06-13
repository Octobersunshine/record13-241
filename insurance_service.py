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


def calculate_total_premium(vehicle: VehicleInfo) -> Dict:
    compulsory_total, compulsory_detail = CompulsoryInsuranceCalculator.calculate(
        vehicle.seats, vehicle.claim_count_last_year, vehicle.claim_free_years
    )
    commercial_total, commercial_detail = CommercialInsuranceCalculator.calculate(vehicle)

    grand_total = round(compulsory_total + commercial_total, 2)

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
        "grand_total": grand_total,
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

        result = calculate_total_premium(vehicle)
        return jsonify({"success": True, "data": result})

    except ValueError as e:
        return jsonify({"error": f"参数格式错误: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "车险保费试算服务"})


def demo():
    demo_cases = [
        VehicleInfo("丰田", 1, 0, claim_free_years=3, purchase_price=200000),
        VehicleInfo("大众", 3, 0, claim_free_years=1, purchase_price=150000),
        VehicleInfo("奔驰", 5, 1, claim_free_years=0, seats=7, purchase_price=500000),
        VehicleInfo("比亚迪", 0, 2, claim_free_years=0, purchase_price=180000, third_party_limit=2000000),
    ]

    print("=" * 70)
    print("车险保费试算服务 - 演示案例 (NCD已修复)")
    print("=" * 70)

    for i, v in enumerate(demo_cases, 1):
        result = calculate_total_premium(v)
        print(f"\n--- 案例 {i}: {v.brand} | 车龄{v.vehicle_age}年 | 上年出险{v.claim_count_last_year}次 | 连续无出险{v.claim_free_years}年 ---")
        print(f"  交强险: {result['compulsory_insurance']['total']:.2f} 元")
        print(f"    基础保费: {result['compulsory_insurance']['base_premium']:.2f} 元")
        print(f"    费率系数: {result['compulsory_insurance']['factor']:.2f}")
        print(f"    车船税:   {result['compulsory_insurance']['vehicle_and_vessel_tax']:.2f} 元")
        print(f"  商业险: {result['commercial_insurance']['total']:.2f} 元")
        ci = result["commercial_insurance"]
        print(f"    无赔款优待系数(NCD): {ci['no_claim_discount_factor']:.2f}")
        print(f"    连续无出险年数:      {ci['consecutive_claim_free_years']}")
        print(f"    品牌系数:            {ci['brand_factor']:.2f}")
        print(f"    车龄系数:            {ci['age_factor']:.2f}")
        print(f"    车损险: {ci['details']['vehicle_loss_insurance']['premium']:.2f} 元")
        print(f"    三者险: {ci['details']['third_party_insurance']['premium']:.2f} 元 (保额{ci['details']['third_party_insurance']['coverage_limit']//10000}万)")
        if "driver_insurance" in ci["details"]:
            print(f"    司机险: {ci['details']['driver_insurance']['premium']:.2f} 元")
        if "passenger_insurance" in ci["details"]:
            print(f"    乘客险: {ci['details']['passenger_insurance']['premium']:.2f} 元")
        if "theft_insurance" in ci["details"]:
            print(f"    盗抢险: {ci['details']['theft_insurance']['premium']:.2f} 元")
        print(f"  ─────────────────────────────")
        print(f"  合计保费: {result['grand_total']:.2f} 元")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        print("启动车险保费试算服务 HTTP API...")
        print("接口: POST http://localhost:5000/api/calculate")
        app.run(host="0.0.0.0", port=5000, debug=False)
    else:
        demo()
