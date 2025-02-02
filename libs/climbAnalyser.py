import pandas as pd
from libs.utils import (
    haversine,
    calcWindComponents,
    isaDiff,
    getPerf,
    loadBook,
    c2f,
    maxSpread,
    engineMetrics,
)


def findClimb(
    flight, modelConfig
):  # select only datapoints where the power indicates a climb
    climbPowerTreshold = modelConfig.loc["climbPowerTreshold", "Value"]
    climbPowerIndicator = modelConfig.loc["climbPowerIndicator", "Value"]
    return flight[flight[climbPowerIndicator] > float(climbPowerTreshold)]


def climbPerformance(flight, model, modelConfig):
    # actual flight performance
    climb = findClimb(flight, modelConfig)
    climbStartAlt = climb["AltPress"].min()
    climbEndAlt = climb["AltPress"].max()
    climbAlt = climbEndAlt - climbStartAlt
    climbUsedFuel = (
        climb["E1 FFlow"].sum() / 3600
    )  # this assumes 1 second measure intervals
    taxiFuel = flight.loc[: climb.index.min()]["E1 FFlow"].sum() / 3600
    totalClimbFuel = (
        climbUsedFuel + taxiFuel
    )  # book table includes taxi and takeoff, so needs to be included here
    climbTime = len(climb) / 60  # assumes 1 second measure interval
    climbPowerIndicator = modelConfig.loc["climbPowerIndicator", "Value"]
    climbISA = isaDiff(
        climb.loc[climb.index.min(), "OAT"], climb.loc[climb.index.min(), "AltPress"]
    ) + isaDiff(
        climb.loc[climb.index.max(), "OAT"], climb.loc[climb.index.max(), "AltPress"]
    )  # taking the average ISA variation across the climb
    climbPower = climb[climbPowerIndicator].mean()
    # book performance
    climbBook = loadBook("climb", model)
    base = getPerf(
        climbBook, [climbPower, climbISA, climbStartAlt], ["time", "fuel", "distance"]
    )
    top = getPerf(
        climbBook, [climbPower, climbISA, climbEndAlt], ["time", "fuel", "distance"]
    )
    bookClimbPerf = top - base
    # summary table
    climbTable = pd.DataFrame(columns=["Actual", "Book", "Variance", "Units"])
    climbTable.loc["Climb Time"] = [
        round(climbTime),
        round(bookClimbPerf[0]),
        round(100 * (climbTime / bookClimbPerf[0] - 1)),
        "minutes",
    ]
    climbTable.loc["Climb Fuel Used"] = [
        round(totalClimbFuel, 1),
        round(bookClimbPerf[1], 1),
        round(100 * (totalClimbFuel / bookClimbPerf[1] - 1)),
        "USG",
    ]
    climbTable.loc["Climb Fuel Used per 10k feet"] = [
        round(totalClimbFuel / climbAlt * 10000, 1),
        round(bookClimbPerf[1] / climbAlt * 10000, 1),
        round(100 * (totalClimbFuel / bookClimbPerf[1] - 1)),
        "USG",
    ]
    climbTable.loc["Climb Average Vertical Speed"] = [
        round(climbAlt / climbTime),
        round(climbAlt / bookClimbPerf[0]),
        round(100 * (1 - climbTime / bookClimbPerf[0])),
        "fpm",
    ]
    climbTable.loc["Climb Average IAS"] = [
        round(climb["IAS"].mean()),
        "-",
        "-",
        "knots",
    ]
    climbTable.loc["Climb Average Power"] = [
        round(climbPower, 1),
        str(climbBook.index.get_level_values(0).min())
        + "-"
        + str(climbBook.index.get_level_values(0).max()),
        "-",
        climbPowerIndicator,
    ]
    if "climbMaxTIT" in modelConfig.index:
        maxClimbTIT = climb[
            (climb["E1 MAP"] < float(modelConfig.loc["cimbMaxTITPowerHigh", "Value"]))
            & (climb["E1 MAP"] > float(modelConfig.loc["cimbMaxTITPowerLow", "Value"]))
        ]["E1 TIT1"].max()
        climbTable.loc["Climb Max TIT"] = [
            round(maxClimbTIT),
            modelConfig.loc["climbMaxTIT", "Value"],
            round(
                100 * (maxClimbTIT / float(modelConfig.loc["climbMaxTIT", "Value"]) - 1)
            ),
            "degrees F",
        ]
    climbTable = engineMetrics(climb, climbTable, modelConfig, "Climb")
    climbTable.loc["Climb Average temp vs ISA"] = [
        round(climbISA, 1),
        "-",
        "-",
        "degrees C",
    ]
    return climbTable
