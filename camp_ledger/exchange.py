"""Daily USD/KRW reference rates; only a date is sent to the fixed provider."""
import json, sqlite3
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.request import urlopen, Request

def get_rate(day, database):
    requested=date.fromisoformat(day)
    if requested>datetime.now(timezone(timedelta(hours=9))).date(): raise ValueError('미래 날짜의 환율은 아직 조회할 수 없습니다.')
    with sqlite3.connect(database,timeout=15) as c:
        c.execute('CREATE TABLE IF NOT EXISTS exchange_rates(day TEXT PRIMARY KEY,body TEXT NOT NULL)')
        cached=c.execute('SELECT body FROM exchange_rates WHERE day=?',(day,)).fetchone()
        if cached:return json.loads(cached[0])
    try:
        req=Request('https://api.frankfurter.dev/v1/'+day+'?base=USD&symbols=KRW',headers={'User-Agent':'CampLedger/1.0'})
        with urlopen(req,timeout=8) as response: result=json.loads(response.read(65536))
        rate=Decimal(str(result['rates']['KRW'])); actual=date.fromisoformat(result['date'])
        if not rate.is_finite() or rate<=0 or actual>requested:raise ValueError()
    except Exception as exc: raise ValueError('환율을 가져오지 못했습니다. 구매일자를 확인하고 잠시 후 다시 시도해주세요.') from exc
    data={'exchange_rate':float(rate),'exchange_date':actual.isoformat(),'source':'Frankfurter · ECB','requested_date':day}
    with sqlite3.connect(database,timeout=15) as c:c.execute('INSERT OR IGNORE INTO exchange_rates VALUES(?,?)',(day,json.dumps(data)))
    return data

def dollar_amount(value):
    try:
        amount=Decimal(str(value))
        if isinstance(value,bool) or not amount.is_finite() or not 0<=amount<=Decimal('999999999') or amount!=amount.quantize(Decimal('.01')):raise ValueError()
    except (InvalidOperation,ValueError):raise ValueError('달러 구매금액은 0 이상, 소수점 두 자리까지 입력해주세요.')
    return amount

def won(amount,rate):return int((dollar_amount(amount)*Decimal(str(rate))).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
