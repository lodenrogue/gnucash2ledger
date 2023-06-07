#! /usr/bin/env python3

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     (1) Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#     (2) Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#
#     (3)The name of the author may not be used to
#     endorse or promote products derived from this software without
#     specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import dateutil.parser
import xml.etree.ElementTree
import gzip

nss = {'gnc': 'http://www.gnucash.org/XML/gnc',
       'act': 'http://www.gnucash.org/XML/act',
       'book': 'http://www.gnucash.org/XML/book',
       'cd': 'http://www.gnucash.org/XML/cd',
       'cmdty': 'http://www.gnucash.org/XML/cmdty',
       'price': 'http://www.gnucash.org/XML/price',
       'slot': 'http://www.gnucash.org/XML/slot',
       'split': 'http://www.gnucash.org/XML/split',
       'sx': 'http://www.gnucash.org/XML/sx',
       'trn': 'http://www.gnucash.org/XML/trn',
       'ts': 'http://www.gnucash.org/XML/ts',
       'fs': 'http://www.gnucash.org/XML/fs',
       'bgt': 'http://www.gnucash.org/XML/bgt',
       'recurrence': 'http://www.gnucash.org/XML/recurrence',
       'lot': 'http://www.gnucash.org/XML/lot',
       'addr': 'http://www.gnucash.org/XML/addr',
       'owner': 'http://www.gnucash.org/XML/owner',
       'billterm': 'http://www.gnucash.org/XML/billterm',
       'bt-days': 'http://www.gnucash.org/XML/bt-days',
       'bt-prox': 'http://www.gnucash.org/XML/bt-prox',
       'cust': 'http://www.gnucash.org/XML/cust',
       'employee': 'http://www.gnucash.org/XML/employee',
       'entry': 'http://www.gnucash.org/XML/entry',
       'invoice': 'http://www.gnucash.org/XML/invoice',
       'job': 'http://www.gnucash.org/XML/job',
       'order': 'http://www.gnucash.org/XML/order',
       'taxtable': 'http://www.gnucash.org/XML/taxtable',
       'tte': 'http://www.gnucash.org/XML/tte',
       'vendor': 'http://www.gnucash.org/XML/vendor', }


class DefaultAttributeProducer:
    def __init__(self, defaultValue):
        self.__defaultValue = defaultValue

    def __getattr__(self, value):
        return self.__defaultValue


def orElse(var, default=''):
    if var is None:
        return DefaultAttributeProducer(default)
    else:
        return var


class Commodity:
    def __init__(self, e):
        """From a XML e representing a commodity, generates a representation of
        the commodity
        """

        self.space = orElse(e.find('cmdty:space', nss)).text
        self.id = orElse(e.find('cmdty:id', nss)).text
        self.name = orElse(e.find('cmdty:name', nss)).text

    def toLedgerFormat(self, indent=0):
        """Format the commodity in a way good to be interpreted by ledger.

        If provided, `indent` will be the indentation (in spaces) of the entry.
        """
        outPattern = ('{spaces}commodity {id}\n'
                      '{spaces}  note {name} ({space}:{id})\n')
        return outPattern.format(spaces=' '*indent, **self.__dict__)


class Account:
    def __init__(self, accountDb, e):
        self.accountDb = accountDb
        self.name = e.find('act:name', nss).text
        self.id = e.find('act:id', nss).text
        self.accountDb[self.id] = self
        self.description = orElse(e.find('act:description', nss)).text
        self.type = e.find('act:type', nss).text
        self.parent = orElse(e.find('act:parent', nss), None).text
        self.used = False  # Mark accounts that were in a transaction
        self.commodity = orElse(e.find('act:commodity/cmdty:id', nss), None).text

    def getParent(self):
        return self.accountDb[self.parent]

    def fullName(self):
        if self.parent is not None and self.getParent().type != 'ROOT':
            prefix = self.getParent().fullName() + ':'
        else:
            prefix = ''  # ROOT will not be displayed
        return prefix + self.name

    def toLedgerFormat(self, indent=0):
        outPattern = ('{spaces}account {fullName}\n'
                      '{spaces}  note {description} (type: {type})\n')
        return outPattern.format(spaces=' '*indent, fullName=self.fullName(),
                                 **self.__dict__)


class Split:
    """Represents a single split in a transaction"""

    def __init__(self, accountDb, e):
        self.accountDb = accountDb
        self.reconciled = e.find('split:reconciled-state', nss).text == 'y'
        self.accountId = e.find('split:account', nss).text
        accountDb[self.accountId].used = True

        # Some special treatment for value and quantity
        rawValue = e.find('split:value', nss).text
        self.value = self.convertValue(rawValue)

        # Quantity is the amount on the commodity of the account
        rawQuantity = e.find('split:quantity', nss).text
        self.quantity = self.convertValue(rawQuantity)

    def getAccount(self):
        return self.accountDb[self.accountId]

    def toLedgerFormat(self, commodity='$', indent=0):
        outPattern = '{spaces}  {flag}{accountName}    {value}'

        # Check if commodity conversion will be needed
        conversion = ''
        if commodity == self.getAccount().commodity:
            value = '{value} {commodity}'.format(commodity=commodity,
                                                 value=self.value)
        else:
            conversion = ' {destValue} "{destCmdty}" @@ {value} {commodity}'
            realValue = self.value[1:] if self.value.startswith('-') else self.value
            value = conversion.format(destValue=self.quantity,
                                      destCmdty=self.getAccount().commodity,
                                      value=realValue,
                                      commodity=commodity)

        return outPattern.format(flag='* ' if self.reconciled else '',
                                 spaces=indent*' ',
                                 accountName=self.getAccount().fullName(),
                                 conversion=conversion,
                                 value=value)

    def convertValue(self, rawValue):
        (intValue, decPoint) = rawValue.split('/')

        n = len(decPoint) - 1
        signFlag = intValue.startswith('-')
        if signFlag:
            intValue = intValue[1:]
        if len(intValue) < n+1:
            intValue = '0'*(n+1-len(intValue)) + intValue
        if signFlag:
            intValue = '-' + intValue
        return intValue[:-n] + '.' + intValue[-n:]

class Transaction:
    def __init__(self, accountDb, e):
        self.accountDb = accountDb
        self.date = dateutil.parser.parse(e.find('trn:date-posted/ts:date',
                                                 nss).text)
        self.commodity = e.find('trn:currency/cmdty:id', nss).text
        self.description = e.find('trn:description', nss).text
        self.splits = [Split(accountDb, s)
                       for s in e.findall('trn:splits/trn:split', nss)]

    def toLedgerFormat(self, indent=0):
        outPattern = ('{spaces}{date} {description}\n'
                      '{splits}\n')
        splits = '\n'.join(s.toLedgerFormat(self.commodity, indent)
                           for s in self.splits)
        return outPattern.format(
            spaces=' '*indent,
            date=self.date.strftime('%Y/%m/%d'),
            description=self.description,
            splits=splits)

def read_file(file_name):
    try:
        with gzip.open(file_name, 'rt') as f:
            return f.read()
    except gzip.BadGzipFile:
        with open(file_name, 'r') as f:
            return f.read()


def convert2Ledger(inputFile):
    """Reads a gnucash file and converts it to a ledger file."""
    file = read_file(inputFile)

    e = xml.etree.ElementTree.fromstring(file)
    b = e.find('gnc:book', nss)

    # Find all commodities
    commodities = []
    for cmdty in b.findall('gnc:commodity', nss):
        commodities.append(Commodity(cmdty))

    # Find all accounts
    accountDb = {}
    for acc in b.findall('gnc:account', nss):
        Account(accountDb, acc)

    # Finally, find all transactions
    transactions = []
    for xact in b.findall('gnc:transaction', nss):
        transactions.append(Transaction(accountDb, xact))

    # Generate output
    output = ''

    # First, add the commodities definition
    output = '\n'.join(c.toLedgerFormat() for c in commodities)
    output += '\n\n'

    # Then, output all accounts
    output += '\n'.join(a.toLedgerFormat()
                        for a in accountDb.values() if a.used)
    output += '\n\n'

    # And finally, output all transactions
    output += '\n'.join(t.toLedgerFormat()
                        for t in sorted(transactions, key=lambda x: x.date))

    return (output, commodities, accountDb, transactions)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        print('Usage: gcash2ledger.py inputXMLFile [outputLedgerFile]\n')
        print('If output is not provided, output to stdout')
        print('If output exists, it will not be overwritten.')
        exit(1)

    if len(sys.argv) == 3 and os.path.exists(sys.argv[2]):
        print('Output file exists. It will not be overwritten.')
        exit(2)

    (data, commodities, accountDb, transactions) = convert2Ledger(sys.argv[1])

    if len(sys.argv) == 3:
        with open(sys.argv[2], 'w') as fh:
            fh.write(data)
    else:
        print(data)

