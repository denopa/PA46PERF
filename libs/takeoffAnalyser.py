import pandas as pd 
from libs.utils import haversine, calcWindComponents, isaDiff, getPerf, loadBook
from configuration.units import runwayUnits


# definitions


def findTakeoff(flight): #returns the row of the takeoff point
    garminGround = flight[flight['OnGrnd'] == 0].index.min() #Garmin Ground indicator
    startAltitude = flight.loc[garminGround,'AltGPS']
    return flight[(flight.index>garminGround)&(flight.AltGPS>startAltitude+3)].index.min()

def find50feet(flight): #returns the row of the takeoff point
    garminGround = flight[flight['OnGrnd'] == 0].index.min() #Garmin Ground indicator
    startAltitude = flight.loc[garminGround,'AltGPS']
    return flight[(flight.index>garminGround)&(flight.AltGPS>startAltitude+50)].index.min()

def findGroundRollStart(groundPortion, modelConfig): #finds the row where take off roll started. This is model dependent
    takeoffPowerTreshold =  float(modelConfig.loc['takeoffPowerTreshold','Value']) #indicates the POWER above which we consider the ground roll to start
    takeoffPowerIndicator = modelConfig.loc['takeoffPowerIndicator','Value']
    return groundPortion[groundPortion[takeoffPowerIndicator]>takeoffPowerTreshold].index.min()

def calcGroundRoll(flight, modelConfig):
    garminGround = flight[flight['OnGrnd'] == 0].index.min() #Garmin Ground indicator
    takeoffPoint = findTakeoff(flight)
    rollStart = findGroundRollStart(flight[:takeoffPoint], modelConfig)
    dist = haversine(flight['Longitude'][rollStart], flight['Latitude'][rollStart],flight['Longitude'][takeoffPoint], flight['Latitude'][takeoffPoint], runwayUnits)
    ais = flight.loc[takeoffPoint, 'IAS']
    temp = flight.loc[rollStart, 'OAT']
    pressAlt = flight.loc[rollStart, 'AltPress']
    windSpeed = flight.loc[garminGround:takeoffPoint, 'WndSpd'].mean()
    windDirection = flight.loc[garminGround:takeoffPoint, 'WndDr'].mean()
    track = flight.loc[garminGround:takeoffPoint, 'TRK'].mean()
    return dist, ais, temp, pressAlt, windSpeed, windDirection, track

def calc50feetDistance(flight, modelConfig):
    fiftyfeetPoint = find50feet(flight)
    rollStart = findGroundRollStart(flight[:fiftyfeetPoint], modelConfig)
    dist = haversine(flight['Longitude'][rollStart], flight['Latitude'][rollStart],flight['Longitude'][fiftyfeetPoint], flight['Latitude'][fiftyfeetPoint], runwayUnits)
    engineType = modelConfig.loc['engineType','Value']
    if engineType == 'piston':
        bookTakeoffMAP = float(modelConfig.loc['takeoffMAP','Value'])
        bookTakeoffRPM = float(modelConfig.loc['takeoffRPM','Value'])
        bookminTakeoffFFlow = float(modelConfig.loc['minTakeoffFFlow','Value'])
        takeoffMAP = flight['E1 MAP'][fiftyfeetPoint-10:fiftyfeetPoint].mean().round(1)
        takeoffRPM = flight['E1 RPM'][fiftyfeetPoint-10:fiftyfeetPoint].mean().round(0)
        takeoffFFlow = flight['E1 FFlow'][fiftyfeetPoint-10:fiftyfeetPoint].mean().round(1)
        engineInfo = pd.DataFrame([[takeoffMAP,bookTakeoffMAP, "inches"],[takeoffRPM,bookTakeoffRPM],[takeoffFFlow,bookminTakeoffFFlow, "gph"]],index=["Take off MAP","Take off RPM","Take off Fuel Flow"], columns=["Actual", "Book","Units"])
        engineInfo["Variance %"] = round(100*( engineInfo.Actual / engineInfo.Book -1))
        engineInfo = engineInfo[['Actual','Book','Variance %','Units']]
    else:
        engineInfo = pd.DataFrame(columns=["Actual", "Book", "Variance %", "Units"])

    return dist, flight['IAS'][fiftyfeetPoint], engineInfo

# MAIN
def takeOffPerformance(flight, model, modelConfig, takeoffMethod, takeoffWeight):
    # load book 
    takeOffRollBook = loadBook('takeOffRoll', model, configuration=takeoffMethod)
    distanceOver50Book = loadBook('distanceOver50', model, configuration=takeoffMethod)
    bookTakeOffIAS = float(modelConfig.loc['takeoffIAS'+takeoffMethod,'Value'])
    bookBarrierIAS = float(modelConfig.loc['barrierIAS'+takeoffMethod,'Value'])
    # actual flight performance
    takeOffRoll, takeOffAIS, temp, pressAlt,  windSpeed, windDirection, track = calcGroundRoll(flight, modelConfig)
    fiftyFeetDistance, barrierIAS, engineInfo = calc50feetDistance(flight, modelConfig)
    headwind, crosswind = calcWindComponents(windSpeed, windDirection, track)
    bookTakeOffRoll = getPerf(takeOffRollBook, [isaDiff(temp, pressAlt), pressAlt, takeoffWeight, headwind], runwayUnits)
    bookDistanceOver50 = getPerf(distanceOver50Book, [isaDiff(temp, pressAlt), pressAlt, takeoffWeight, headwind], runwayUnits)
# summary table
    takeoffTable = pd.DataFrame(columns=['Actual','Book','Variance %', 'Units'])
    takeoffTable.loc['Take off IAS'] = [int(takeOffAIS), int(bookTakeOffIAS),round(100*(takeOffAIS/bookTakeOffIAS-1)), 'knots']
    takeoffTable.loc['Take off Roll'] = [int(takeOffRoll), int(bookTakeOffRoll),round(100*(takeOffRoll/bookTakeOffRoll-1)), runwayUnits]
    takeoffTable.loc['Distance over 50 feet'] = [int(fiftyFeetDistance), int(bookDistanceOver50), round(100*(fiftyFeetDistance/bookDistanceOver50-1)), runwayUnits]
    takeoffTable.loc['AIS over Barrier'] = [int(barrierIAS), int(bookBarrierIAS), round(100*(barrierIAS/bookBarrierIAS-1)), "knots"]
    takeoffTable.loc['Headwind'] = [round(headwind),'-','-','knots']
    takeoffTable.loc['Crosswind'] = [round(crosswind), '-','-','knots']
    takeoffTable.loc['Temp vs ISA'] = [round(isaDiff(temp, pressAlt)), '-','-','degrees C']
    takeoffTable.loc['Pressure Altitude'] = [pressAlt, '-','-','feet']
    if len(engineInfo)>0:
        takeoffTable = pd.concat([takeoffTable, engineInfo])
    return takeoffTable

