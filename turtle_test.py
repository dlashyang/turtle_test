import time
import csv
from collections import deque

ENTER_PERIOD = 20
EXIT_PERIOD = 10
STOP_FACTOR = 2
MAX_UNIT = 2
LOG_LEVEL = 2

def print_log(msg="", level=1):
    if (level<=LOG_LEVEL):
        print (msg)

class account(object):
    def __init__(self, strategy, price, size=200000):
        print("account init.")
        self.balance = size
        self.equity = size
        self.strategy = strategy
        self.price_ins = price
        self.holding = 0
        self.holding_unit = 0
        self.stop_price = 0

    def get_unit_size(self, price):
        self.equity = self.balance + self.holding * price
        return self.equity*0.01/self.price_ins.get_ATR()

    def buy(self, ref_price):
        if (self.holding_unit >= self.strategy.max_unit):
            print_log("%s: cannot buy, holding unit %d is full." %(self.price_ins.date, self.holding_unit), 3)
            return

        bought_price = sum(ref_price)/2
        unit_size = self.get_unit_size(bought_price)
        investing = unit_size * bought_price

        if (self.balance >= investing):
            self.balance -= investing
            self.holding += unit_size
            self.holding_unit += 1
            self.stop_price = bought_price - self.strategy.stop_factor*self.price_ins.get_ATR()
            print_log("%s: bought %f at %f, stop at %f. balance is %f" %(self.price_ins.date, unit_size, bought_price, self.stop_price, self.balance), 2)
        else:
            print_log("%s: cannot buy %f at %f, balance %f is not enough" %(self.price_ins.date, unit_size, bought_price, self.balance), 3)

    def sell(self, ref_price):
        if (self.holding == 0):
            return

        sold_price = sum(ref_price)/2
        income = self.holding * sold_price

        self.balance += income
        self.equity = self.balance
        print_log("%s: sold %f at %f (stop %f). balance is %f" %(self.price_ins.date, self.holding, sold_price, self.stop_price, self.balance), 2)

        self.holding = 0
        self.holding_unit = 0
        self.stop_price = 0
        
    def trade(self):
        if (not self.price_ins.is_data_ready()):
            print_log("%s: data is not ready" % self.price_ins.date, 5)
            return

        ref_price = self.strategy.trade_signal("break_out")
        if (ref_price != None):
            print_log("%s: got break_out: %f %f" % (self.price_ins.date,ref_price[0],ref_price[1]), 3)
            self.buy(ref_price)
            return

        ref_price = self.strategy.trade_signal("winning_exit")
        if (ref_price != None):
            print_log("%s: got exit: %f %f" % (self.price_ins.date,ref_price[0],ref_price[1]), 3)
            self.sell(ref_price)
            return

        ref_price = self.strategy.trade_signal("stop", self.stop_price)
        if (ref_price != None):
            print_log("%s: got stop: %f %f" % (self.price_ins.date,ref_price[0],ref_price[1]), 3)
            self.sell(ref_price)
            return

        print_log("%s: no signal" % self.price_ins.date, 5)

class trade_strategy(object):
    def __init__(self, price, enter_prd=20, exit_prd=10, max_unit=4, need_stop=1, stop_factor=2):
        self.enter_period = enter_prd
        self.exit_period = exit_prd
        self.max_unit = max_unit
        self.need_stop = need_stop
        self.stop_factor = stop_factor
        self.price = price

    # return None if no signal; return related prices if there is signal
    def trade_signal(self, signal_type, stop_price=0):
        #before trade starting, we are sure data is ready
        ret = None
        if (signal_type == "break_out"):
            period_high = self.price.get_data("highest", self.enter_period)
            high_today = self.price.get_data("latest_high")
            ret = (high_today, period_high) if high_today>period_high else None
        elif (signal_type == "winning_exit"):
            period_low = self.price.get_data("lowest", self.exit_period)
            low_today = self.price.get_data("latest_low")
            ret = (low_today, period_low) if low_today<period_low else None
        elif ((signal_type == "stop") and (self.need_stop == 1)):
            low_today = self.price.get_data("latest_low")
            ret = (low_today, stop_price) if low_today<stop_price else None
        else:
            pass

        return ret

class prices(object):
    def __init__(self, data_size):
        self.high = deque(maxlen=data_size)
        self.low = deque(maxlen=data_size)
        self.pre_close = deque(maxlen=data_size)
        self.TR = deque(maxlen=data_size)

    def update_from_csv(self, raw_data):
        [date,pre_Close_Price,highest_Price,lowest_Price]=raw_data
        if (highest_Price == "0"):
            print_log("%s: no valid data" % date, 1)
            return
        self.update([date, float(highest_Price), float(lowest_Price), float(pre_Close_Price)])

    def update(self, price):
        [date, high, low, pre_close] = price
        self.high.append(high)
        self.low.append(low)
        self.pre_close.append(pre_close)
        self.date = date
        self.TR.append(max(high-low,abs(high-pre_close),abs(pre_close-low)))
        print_log("%s: high %f; low %f; pre_close %f; TR %f; ATR %f" % (date, high, low, pre_close, self.TR[-1], self.get_ATR()), 5)

    def get_data(self, data_type, range=1):
        if (data_type == "latest_high"):
            print_log("%s: latest high is %f" % (self.date,self.high[-1]),5)
            return self.high[-1]
        elif (data_type == "latest_low"):
            print_log("%s: latest low is %f" % (self.date,self.low[-1]),5)
            return self.low[-1]
        elif (data_type == "highest"):
            print_log("%s: last %d days highest is %f" % (self.date, range, max(list(self.high)[-(range+1):-1])),5)
            return max(list(self.high)[-(range+1):-1]) 
        elif (data_type == "lowest"):
            print_log("%s: last %d days lowest is %f" % (self.date, range, min(list(self.low)[-(range+1):-1])),5)
            return min(list(self.low)[-(range+1):-1]) 
        else:
            return

    def is_data_ready(self):
        #ATP calculatuion needs 20 days
        return self.high.maxlen == len(self.high)
        
    def get_ATR(self):
        if (self.is_data_ready()):
            return sum(list(self.TR)[-20:])/20
        else:
            return 0

def main():
    price = prices(max(ENTER_PERIOD, EXIT_PERIOD))
    strategy = trade_strategy(price, ENTER_PERIOD, EXIT_PERIOD, MAX_UNIT, 1, STOP_FACTOR)
    my_account = account(strategy, price)

    print_log("Enter %d days; Exit %d days; Max unit %d; Stop factor: %d" %(ENTER_PERIOD, EXIT_PERIOD, MAX_UNIT, STOP_FACTOR),1)
    with open('31.csv', newline='') as csvfile:
        price_data = csv.reader(csvfile, delimiter=',')
        for day in price_data:
            if (day[0] == "tradeDate"):
                continue

            price.update_from_csv(day)
            my_account.trade()
        
        print_log ("Now we have $%f" % my_account.balance)

if __name__ == '__main__':
    main()