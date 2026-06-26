"""阶段二演示数据：为 dev.db 灌入交通/活动/特产三类资源的内蒙古示例数据。

特点：
- 幂等：以 (name, city) 判重，重复运行不会重复插入。
- 仅依赖三张新表（transportation / activity / specialty），不影响既有数据。

运行方式：
    cd backend
    python -m scripts.seed_phase2_resources
"""

from __future__ import annotations

from app import create_app
from app.db import db
from app.models import Activity, Specialty, Transportation

TRANSPORTATIONS = [
    dict(name="呼和浩特白塔国际机场", city="呼和浩特", district="赛罕区", address="机场路", longitude=111.824, latitude=40.851, transport_type="机场", phone="0471-96777", operating_hours="航班时刻为准", price_info="机场大巴约20元/打车约50元", rating_avg=4.4, rating_count=120, tags="机场;枢纽", description="呼和浩特主要航空枢纽，连接区内外主要城市。", source="seed"),
    dict(name="呼和浩特站", city="呼和浩特", district="回民区", address="车站西街", longitude=111.668, latitude=40.842, transport_type="火车站", phone="12306", operating_hours="05:30-23:30", price_info="市内公交2元/打车约15元", rating_avg=4.2, rating_count=90, tags="火车站;高铁", description="呼和浩特铁路客运主站，普速与动车均可乘坐。", source="seed"),
    dict(name="包头站", city="包头", district="昆都仑区", address="站前路", longitude=109.823, latitude=40.658, transport_type="火车站", phone="12306", operating_hours="06:00-23:00", price_info="市内公交2元/打车约15元", rating_avg=4.1, rating_count=70, tags="火车站", description="包头市主要铁路客运站。", source="seed"),
    dict(name="呼伦贝尔海拉尔东山国际机场", city="呼伦贝尔", district="海拉尔区", address="东山", longitude=119.825, latitude=49.205, transport_type="机场", phone="0470-8217777", operating_hours="航班时刻为准", price_info="机场大巴约15元/打车约40元", rating_avg=4.3, rating_count=60, tags="机场", description="呼伦贝尔草原旅游的主要空中门户。", source="seed"),
    dict(name="响沙湾景区接驳车", city="鄂尔多斯", district="达拉特旗", address="响沙湾旅游区", longitude=109.989, latitude=40.281, transport_type="接驳车", phone="0477-3961888", operating_hours="08:30-18:00", price_info="景区内接驳约30元", rating_avg=4.0, rating_count=45, tags="接驳车;景区交通", description="连接响沙湾各游览区的景区摆渡交通。", source="seed"),
    dict(name="赤峰站", city="赤峰", district="红山区", address="站前街", longitude=118.95, latitude=42.27, transport_type="火车站", phone="12306", operating_hours="06:00-23:00", price_info="公交2元/打车约15元", rating_avg=4.1, rating_count=55, tags="火车站;直达", description="赤峰市铁路客运主站，直达多地、换乘便捷。", source="seed"),
    dict(name="通辽站", city="通辽", district="科尔沁区", address="交通路", longitude=122.26, latitude=43.65, transport_type="火车站", phone="12306", operating_hours="06:00-23:00", price_info="公交2元/打车约15元", rating_avg=4.0, rating_count=48, tags="火车站;枢纽", description="通辽市铁路客运枢纽。", source="seed"),
    dict(name="乌兰察布站", city="乌兰察布", district="集宁区", address="泉山路", longitude=113.13, latitude=41.03, transport_type="高铁站", phone="12306", operating_hours="06:00-22:30", price_info="公交2元/打车约12元", rating_avg=4.3, rating_count=66, tags="高铁站;直达;便捷", description="京呼高铁重要站点，直达北京，少换乘。", source="seed"),
    dict(name="乌海机场", city="乌海", district="海勃湾区", address="机场路", longitude=106.80, latitude=39.79, transport_type="机场", phone="0473-3998888", operating_hours="航班时刻为准", price_info="打车约40元", rating_avg=4.0, rating_count=30, tags="机场", description="乌海市民用支线机场。", source="seed"),
    dict(name="乌兰浩特机场", city="兴安盟", district="乌兰浩特市", address="义勒力特镇", longitude=122.02, latitude=46.20, transport_type="机场", phone="0482-8999999", operating_hours="航班时刻为准", price_info="机场大巴约15元", rating_avg=4.1, rating_count=34, tags="机场;接驳", description="兴安盟航空门户，含市区接驳大巴。", source="seed"),
    dict(name="锡林浩特机场", city="锡林郭勒", district="锡林浩特市", address="机场路", longitude=115.97, latitude=43.92, transport_type="机场", phone="0479-8669999", operating_hours="航班时刻为准", price_info="打车约30元", rating_avg=4.0, rating_count=28, tags="机场", description="锡林郭勒草原旅游空中通道。", source="seed"),
    dict(name="巴彦淖尔站", city="巴彦淖尔", district="临河区", address="车站路", longitude=107.39, latitude=40.74, transport_type="火车站", phone="12306", operating_hours="06:00-23:00", price_info="公交2元/打车约12元", rating_avg=4.0, rating_count=40, tags="火车站", description="巴彦淖尔市铁路客运站。", source="seed"),
    dict(name="阿拉善左旗汽车站", city="阿拉善盟", district="巴彦浩特镇", address="额鲁特东路", longitude=105.69, latitude=38.83, transport_type="汽车站", phone="0483-8222222", operating_hours="06:30-19:00", price_info="按线路计价", rating_avg=3.9, rating_count=22, tags="汽车站;接驳", description="阿拉善盟公路客运及景区接驳枢纽。", source="seed"),
]

ACTIVITIES = [
    dict(name="锡林郭勒那达慕大会", city="锡林郭勒", district="锡林浩特市", address="那达慕会场", longitude=116.086, latitude=43.933, activity_type="节庆", phone="0479-8826666", hold_time="每年7月中下旬", price_info="部分项目免费/部分80-160元", rating_avg=4.8, rating_count=210, tags="亲子;年轻人;民俗", description="集赛马、摔跤、射箭于一体的草原传统盛会，适合全家共同体验草原文化。", source="seed"),
    dict(name="昭君文化节", city="呼和浩特", district="玉泉区", address="昭君博物院", longitude=111.66, latitude=40.74, activity_type="节庆", phone="0471-12345", hold_time="每年8月", price_info="门票约65元", rating_avg=4.5, rating_count=150, tags="文化;中老年;亲子", description="以昭君出塞为主题的文化节庆，含展览、演出与民俗活动。", source="seed"),
    dict(name="呼伦贝尔冰雪那达慕", city="呼伦贝尔", district="海拉尔区", address="呼伦贝尔冰雪基地", longitude=119.73, latitude=49.21, activity_type="节庆", phone="0470-8217000", hold_time="每年12月至次年2月", price_info="约120元", rating_avg=4.6, rating_count=130, tags="年轻人;户外;冰雪", description="冬季草原冰雪主题活动，含雪地赛马、冰雪娱乐等项目。", source="seed"),
    dict(name="鄂尔多斯草原音乐节", city="鄂尔多斯", district="康巴什区", address="草原演艺中心", longitude=109.79, latitude=39.61, activity_type="演出", phone="0477-8500000", hold_time="每年6月", price_info="180-580元", rating_avg=4.4, rating_count=98, tags="年轻人;音乐;夜场", description="草原主题户外音乐演出，适合喜爱热闹氛围的年轻群体。", source="seed"),
    dict(name="内蒙古博物院特展", city="呼和浩特", district="赛罕区", address="东影南路27号", longitude=111.702, latitude=40.807, activity_type="展览", phone="0471-4614615", hold_time="常年（特展不定期）", price_info="免费（部分特展收费）", rating_avg=4.7, rating_count=260, tags="文化;中老年;亲子;安静", description="以草原文明为核心的主题展览，环境安静、适合文化体验型游客。", source="seed"),
    dict(name="包头草原文化旅游节", city="包头", district="昆都仑区", address="赛汗塔拉城中草原", longitude=109.84, latitude=40.62, activity_type="节庆", phone="0472-5155555", hold_time="每年7-8月", price_info="部分免费/部分60元", rating_avg=4.5, rating_count=140, tags="亲子;民俗;文化", description="城市草原上的民俗与亲子主题节庆。", source="seed"),
    dict(name="赤峰红山文化节", city="赤峰", district="红山区", address="红山公园", longitude=118.96, latitude=42.29, activity_type="节庆", phone="0476-8315555", hold_time="每年8月", price_info="约50元", rating_avg=4.4, rating_count=120, tags="文化;中老年;历史", description="以红山文化为主题的文化节庆，适合文化体验与中老年游客。", source="seed"),
    dict(name="科尔沁草原文化节", city="通辽", district="科尔沁区", address="珠日河草原", longitude=121.80, latitude=43.90, activity_type="节庆", phone="0475-8266666", hold_time="每年7月", price_info="80-150元", rating_avg=4.5, rating_count=130, tags="亲子;民俗;户外", description="科尔沁草原民俗盛会，含赛马、摔跤等。", source="seed"),
    dict(name="察哈尔火山草原旅游节", city="乌兰察布", district="察哈尔右翼后旗", address="乌兰哈达火山地质公园", longitude=112.71, latitude=41.65, activity_type="节庆", phone="0474-3998888", hold_time="每年6-9月", price_info="约90元", rating_avg=4.6, rating_count=160, tags="年轻人;户外;摄影", description="火山地貌主题户外活动，适合年轻人打卡与摄影。", source="seed"),
    dict(name="乌海湖帆船赛", city="乌海", district="海勃湾区", address="乌海湖", longitude=106.78, latitude=39.62, activity_type="赛事", phone="0473-3996666", hold_time="每年9月", price_info="免费观赛", rating_avg=4.3, rating_count=70, tags="年轻人;户外;赛事", description="沙漠中的水上帆船赛事，活力十足。", source="seed"),
    dict(name="阿尔山圣水节", city="兴安盟", district="阿尔山市", address="阿尔山国家森林公园", longitude=119.94, latitude=47.18, activity_type="节庆", phone="0482-7102222", hold_time="每年6月", price_info="约100元", rating_avg=4.6, rating_count=110, tags="文化;民俗;亲子", description="阿尔山温泉与民俗结合的传统节庆。", source="seed"),
    dict(name="河套文化节", city="巴彦淖尔", district="临河区", address="河套文化广场", longitude=107.39, latitude=40.76, activity_type="节庆", phone="0478-8662222", hold_time="每年9月", price_info="免费", rating_avg=4.3, rating_count=85, tags="文化;中老年;亲子", description="展示河套农耕与黄河文化的节庆活动。", source="seed"),
    dict(name="阿拉善英雄会", city="阿拉善盟", district="阿拉善左旗", address="腾格里沙漠那达慕基地", longitude=105.35, latitude=38.95, activity_type="赛事", phone="0483-8266666", hold_time="每年10月", price_info="180-380元", rating_avg=4.7, rating_count=220, tags="年轻人;户外;赛事;夜场", description="沙漠越野与音乐狂欢的大型户外赛事，适合年轻人。", source="seed"),
]

SPECIALTIES = [
    dict(name="蒙古族奶豆腐", city="呼和浩特", district="玉泉区", address="塞上老街特产店", longitude=111.66, latitude=40.81, category="奶制品", phone="0471-6300000", business_hours="09:00-21:00", price_info="约30-60元/份", rating_avg=4.6, rating_count=180, tags="奶制品;伴手礼;地道", description="传统蒙古族奶制品，口感醇厚，适合作为伴手礼带回。", source="seed"),
    dict(name="科尔沁牛肉干", city="通辽", district="科尔沁区", address="霍林河大街特产城", longitude=122.26, latitude=43.61, category="食品", phone="0475-8800000", business_hours="09:00-20:00", price_info="约80-160元/袋", rating_avg=4.7, rating_count=220, tags="牛肉;伴手礼;必买", description="风干牛肉干，肉质紧实、风味浓郁，内蒙古经典特产。", source="seed"),
    dict(name="锡林郭勒马奶酒", city="锡林郭勒", district="锡林浩特市", address="牧民合作社", longitude=116.07, latitude=43.94, category="酒类", phone="0479-8800001", business_hours="10:00-20:00", price_info="约120-260元/瓶", rating_avg=4.3, rating_count=70, tags="马奶酒;民俗;特色", description="传统发酵马奶酒，具有浓郁草原民俗风味。", source="seed"),
    dict(name="呼伦贝尔蒙古银器", city="呼伦贝尔", district="海拉尔区", address="中央街手工艺店", longitude=119.73, latitude=49.21, category="手工艺", phone="0470-8200000", business_hours="09:30-20:30", price_info="约200-2000元", rating_avg=4.5, rating_count=88, tags="手工艺;银器;礼品", description="蒙古族传统银饰与器物，工艺精美，适合收藏与馈赠。", source="seed"),
    dict(name="鄂尔多斯沙棘汁", city="鄂尔多斯", district="东胜区", address="鄂尔多斯大街特产店", longitude=109.99, latitude=39.82, category="食品", phone="0477-8500001", business_hours="09:00-21:00", price_info="约40-90元/箱", rating_avg=4.4, rating_count=110, tags="饮品;健康;伴手礼", description="本地沙棘加工饮品，酸甜可口、富含维生素。", source="seed"),
    dict(name="包头莜面", city="包头", district="昆都仑区", address="钢铁大街特产城", longitude=109.84, latitude=40.66, category="食品", phone="0472-2155555", business_hours="09:00-20:00", price_info="约20-50元/袋", rating_avg=4.4, rating_count=95, tags="面食;地道;伴手礼", description="内蒙古传统莜面，做法多样、健康耐饥。", source="seed"),
    dict(name="赤峰荞麦制品", city="赤峰", district="红山区", address="步行街特产店", longitude=118.96, latitude=42.27, category="食品", phone="0476-8312345", business_hours="09:00-20:00", price_info="约25-60元", rating_avg=4.3, rating_count=88, tags="荞麦;健康;伴手礼", description="赤峰荞麦面、荞麦枕等系列产品。", source="seed"),
    dict(name="乌兰察布马铃薯", city="乌兰察布", district="集宁区", address="恩和路特产店", longitude=113.13, latitude=41.03, category="食品", phone="0474-8222345", business_hours="08:30-19:30", price_info="约15-40元", rating_avg=4.2, rating_count=76, tags="土特产;地道", description="“中国薯都”乌兰察布的优质马铃薯及其制品。", source="seed"),
    dict(name="乌海葡萄", city="乌海", district="海勃湾区", address="黄河西街特产店", longitude=106.79, latitude=39.66, category="食品", phone="0473-3992345", business_hours="09:00-20:00", price_info="约30-80元", rating_avg=4.5, rating_count=102, tags="水果;特色;必买", description="乌海日照充足，出产甘甜葡萄及葡萄酒。", source="seed"),
    dict(name="阿尔山矿泉水", city="兴安盟", district="阿尔山市", address="温泉街特产店", longitude=119.94, latitude=47.18, category="食品", phone="0482-7102345", business_hours="09:00-20:00", price_info="约20-50元/箱", rating_avg=4.4, rating_count=90, tags="饮品;健康;伴手礼", description="阿尔山天然矿泉水，水质优良。", source="seed"),
    dict(name="河套面粉", city="巴彦淖尔", district="临河区", address="河套文化广场特产店", longitude=107.39, latitude=40.74, category="食品", phone="0478-8662345", business_hours="08:30-19:30", price_info="约30-70元", rating_avg=4.5, rating_count=130, tags="粮油;地道;必买", description="河套平原优质小麦磨制的面粉，远近闻名。", source="seed"),
    dict(name="阿拉善苁蓉", city="阿拉善盟", district="巴彦浩特镇", address="额鲁特东路特产店", longitude=105.69, latitude=38.83, category="食品", phone="0483-8222345", business_hours="09:00-20:00", price_info="约80-300元", rating_avg=4.4, rating_count=64, tags="滋补;特色;礼品;必买", description="阿拉善肉苁蓉，沙漠人参，适合馈赠长辈。", source="seed"),
    dict(name="阿拉善玛瑙工艺品", city="阿拉善盟", district="巴彦浩特镇", address="奇石城", longitude=105.70, latitude=38.84, category="手工艺", phone="0483-8226789", business_hours="09:30-20:00", price_info="约100-2000元", rating_avg=4.3, rating_count=58, tags="手工艺;礼品;收藏", description="阿拉善玛瑙与奇石工艺品，精美可收藏馈赠。", source="seed"),
]


def _seed(model, rows) -> int:
    created = 0
    for row in rows:
        exists = model.query.filter_by(name=row["name"], city=row["city"]).first()
        if exists is None:
            db.session.add(model(**row))
            created += 1
    return created


def seed() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        t = _seed(Transportation, TRANSPORTATIONS)
        a = _seed(Activity, ACTIVITIES)
        s = _seed(Specialty, SPECIALTIES)
        db.session.commit()
        print(
            f"seeded transportation+={t} (total {Transportation.query.count()}), "
            f"activity+={a} (total {Activity.query.count()}), "
            f"specialty+={s} (total {Specialty.query.count()})"
        )


if __name__ == "__main__":
    seed()
