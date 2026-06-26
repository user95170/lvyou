from __future__ import annotations

from app import create_app
from app.db import db
from app.models import ScenicSpot, User


def seed() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()

        # Inner Mongolia scenic spots
        im_spots = [
            dict(name="大召寺", city="呼和浩特", address="玉泉区大召前街西口南50米", longitude=111.654, latitude=40.807, category="temple", description="呼和浩特著名藏传佛教寺院"),
            dict(name="内蒙古博物院", city="呼和浩特", address="赛罕区东影南路27号", longitude=111.702, latitude=40.807, category="museum", description="自治区级综合性博物馆"),
            dict(name="五当召", city="包头", address="石拐区白芨沟乡境内", longitude=110.18, latitude=41.11, category="temple", description="清康熙年间建成的藏传佛教寺院"),
            dict(name="响沙湾", city="鄂尔多斯", address="达拉特旗响沙湾旅游景区", longitude=109.989, latitude=40.281, category="desert", description="库布其沙漠观光胜地"),
            dict(name="成吉思汗陵", city="鄂尔多斯", address="伊金霍洛旗伊金霍洛镇", longitude=109.747, latitude=39.573, category="mausoleum", description="纪念成吉思汗的文化圣地"),
            dict(name="呼伦湖", city="呼伦贝尔", address="新巴尔虎左旗境内", longitude=117.5, latitude=48.5, category="lake", description="北方第一大湖"),
            dict(name="额尔古纳湿地", city="呼伦贝尔", address="额尔古纳市拉布大林镇", longitude=120.193, latitude=50.241, category="wetland", description="亚洲第一湿地"),
            dict(name="阿斯哈图石林", city="赤峰", address="克什克腾旗乌兰布统南部", longitude=117.542, latitude=43.266, category="geopark", description="世界地质公园奇石群"),
            dict(name="锡林浩特贝子庙", city="锡林郭勒", address="锡林浩特市", longitude=116.07, latitude=43.94, category="temple", description="藏传佛教寺庙群"),
            dict(name="大青沟自然保护区", city="通辽", address="科尔沁左翼后旗甘旗卡镇", longitude=122.21, latitude=42.93, category="nature_reserve", description="国家级自然保护区"),
            dict(name="乌梁素海", city="巴彦淖尔", address="临河区西南", longitude=108.86, latitude=40.75, category="lake", description="黄河三角洲重要湿地"),
            dict(name="辉腾锡勒草原", city="乌兰察布", address="察哈尔右翼中旗", longitude=112.94, latitude=41.9, category="grassland", description="高山草甸草原风光"),
            dict(name="金沙湾景区", city="乌海", address="海勃湾区黄河西岸", longitude=106.79, latitude=39.66, category="desert", description="黄河沿岸沙漠景观"),
            dict(name="腾格里沙漠·通湖草原", city="阿拉善盟", address="阿拉善左旗巴彦浩特镇北", longitude=105.2, latitude=38.8, category="desert", description="沙漠与草原交织景观"),
            dict(name="居延海", city="阿拉善盟", address="额济纳旗西北", longitude=101.04, latitude=41.99, category="lake", description="候鸟迁徙通道"),
        ]
        for s in im_spots:
            exists = ScenicSpot.query.filter_by(name=s["name"], city=s["city"]).first()
            if not exists:
                db.session.add(ScenicSpot(**s))

        # Inner Mongolia hotels (sample)
        from app.models import Hotel, FoodPlace
        hotels = [
            dict(name="呼和浩特香格里拉大酒店", city="呼和浩特", address="新城区兴安北路5号", longitude=111.67, latitude=40.82, star_level="五星", avg_price=780, rating_avg=None, rating_count=0, tags="商务;豪华", source="seed"),
            dict(name="包头香格里拉大酒店", city="包头", address="青山区钢铁大街66号", longitude=109.84, latitude=40.66, star_level="五星", avg_price=680, rating_avg=None, rating_count=0, tags="商务;会议", source="seed"),
            dict(name="鄂尔多斯皇冠假日酒店", city="鄂尔多斯", address="康巴什新区", longitude=109.79, latitude=39.61, star_level="五星", avg_price=620, rating_avg=None, rating_count=0, tags="休闲;亲子", source="seed"),
            dict(name="呼伦贝尔友谊国际酒店", city="呼伦贝尔", address="海拉尔区", longitude=119.75, latitude=49.22, star_level="四星", avg_price=420, rating_avg=None, rating_count=0, tags="旅游;草原", source="seed"),
            dict(name="赤峰万达嘉华酒店", city="赤峰", address="红山区万达广场附近", longitude=118.95, latitude=42.27, star_level="四星", avg_price=460, rating_avg=None, rating_count=0, tags="商务;购物", source="seed"),
        ]
        for h in hotels:
            exists = Hotel.query.filter_by(name=h["name"], city=h["city"]).first()
            if not exists:
                db.session.add(Hotel(**h))

        # Inner Mongolia foods (sample)
        foods = [
            dict(name="内蒙古手把肉（呼市）", city="呼和浩特", address="赛罕区大学东街", longitude=111.68, latitude=40.82, cuisine_type="蒙餐", avg_price=80, rating_avg=None, rating_count=0, tags="羊肉;手把肉", source="seed"),
            dict(name="牛羊杂碎汤（包头）", city="包头", address="青山区钢铁大街", longitude=109.85, latitude=40.65, cuisine_type="地方小吃", avg_price=35, rating_avg=None, rating_count=0, tags="老字号", source="seed"),
            dict(name="烤全羊（鄂尔多斯）", city="鄂尔多斯", address="东胜区鄂尔多斯大街", longitude=109.99, latitude=39.82, cuisine_type="蒙餐", avg_price=120, rating_avg=None, rating_count=0, tags="团餐;草原风味", source="seed"),
            dict(name="莜面（呼伦贝尔）", city="呼伦贝尔", address="海拉尔区中央街", longitude=119.73, latitude=49.21, cuisine_type="地方小吃", avg_price=45, rating_avg=None, rating_count=0, tags="面食", source="seed"),
        ]
        for f in foods:
            exists = FoodPlace.query.filter_by(name=f["name"], city=f["city"]).first()
            if not exists:
                db.session.add(FoodPlace(**f))

        # demo user (optional)
        demo_user = User.query.filter_by(username="demo").first()
        if not demo_user:
            demo_user = User(username="demo", email="demo@example.com", register_source="seed")
            demo_user.set_password("demo123")
            db.session.add(demo_user)

        db.session.commit()
        print("seed completed")


if __name__ == "__main__":
    seed()
