import csv
from decimal import Decimal

DENOM_EXPONENTS = {
    "ATOM": 0,
    "uatom": 6,
    "OSMO": 0,
    "uosmo": 6,
}


def writeRefundsCsv(refund_amounts: dict):
    header = ["address", "amount"]
    refund_sum = 0
    with open("refunds.csv", "w") as f:
        # create the csv writer
        writer = csv.writer(f)
        writer.writerow(header)

        for k in refund_amounts.items():
            _, refund_amount = k
            writer.writerow(k)
            refund_sum += refund_amount

        writer.writerow(["Total Refund Amount", refund_sum])


def getRefundAmountsFromCSV(file_obj, denom):
    refund_amounts = {}
    refund_reader = csv.reader(file_obj, delimiter=",", quotechar="|")
    denom_multiplier = 10 ** DENOM_EXPONENTS.get(denom, 1)
    for row in refund_reader:
        if "address" in row[0]:
            continue
        delegation_addr = row[0]
        refund_amt = Decimal(row[3]) * denom_multiplier
        refund_amounts[delegation_addr] = refund_amt

    return refund_amounts
