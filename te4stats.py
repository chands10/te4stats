from bs4 import BeautifulSoup
from html2image import Html2Image
import os
from dotenv import load_dotenv
import cv2
import numpy as np
from datetime import datetime
from matplotlib import pyplot as plt


scriptDir = os.path.dirname(os.path.abspath(__file__))
TRACKBO1 = False
SHOWALLONLINE = False


surfaces = {}
def findSurface(court):
    global surfaces
    if court in surfaces:
        return surfaces[court]
    return None


def loadSurfaces():
    global surfaces
    modDir = os.getenv("MOD_DIR")
    found = False
    for d in os.listdir(modDir):
        xktDir = f"{modDir}/{d}"
        if "XKT" in os.listdir(xktDir):
            found = True
            break
    if not found:
        raise Exception("Could not find XKT directory")

    surfacesDir = f"{xktDir}/XKT/Courts/Surfaces"
    for courtDir in os.listdir(surfacesDir):
        foundSurface = False
        foundName = False
        with open(f"{surfacesDir}/{courtDir}/Surface.ini") as surfaceFile:
            for line in surfaceFile:
                if foundSurface and foundName:
                    break

                line = line.strip()
                if not foundSurface and line.startswith("Type"):
                    foundSurface = True
                    surface = line[line.index("// ") + 3:]
                elif not foundName and line.startswith("NameDirect"):
                    foundName = True
                    court = line[line.index("=") + 1:].strip()

        if not foundSurface:
            raise Exception(f"Could not find surface for {courtDir}")
        if not foundName:
            raise Exception(f"Could not find name for {courtDir}")
        
        assert surface in ["Hard", "Synthetic", "Clay", "Grass"]
        if surface == "Synthetic":
            surface = "Hard"
        surfaces[court] = surface


class Player:
    def __init__(self, name):
        self.name = name
        
    def __str__(self):
        return str(vars(self))


class H2HPlayer:
    def __init__(self, name):
        self.name = name
        self.wins = []
        self.numWins = []
        self.longestStreak = 0
        self.longestStreakSets = 0
    
    
    def __str__(self):
        return str(vars(self))
    
    
    def numBOSWins(self, s):
        return len([w for w in self.wins if w.numSets == s])
    
    def numSurfaceWins(self, surface):
        return len([w for w in self.wins if w.surface == surface])
    
    def numBOSSurfaceWins(self, s, surface):
        return len([w for w in self.wins if w.numSets == s and w.surface == surface])


class Match:
    def __init__(self, winner, loser, score, court, time, fakeTime, datetimeString, online):
        self.winner = winner
        self.loser = loser
        self.score = score
        self.numSets, self.setWinners = self.parseSets()
        self.court = court
        self.surface = findSurface(court)
        self.time = time
        self.fakeTime = fakeTime
        self.datetimeString = datetimeString
        self.datetime = datetime.strptime(self.datetimeString, "%Y-%m-%d %H:%M")
        self.online = online

        
    def __str__(self):
        return f"{str(self.winner)=}, {str(self.loser)=}, {str(vars(self))}"
    

    # return True if if first score, else False. -1 on error
    def _findSetWinner(self, score):
        if score == "ret.":
            return -1
        games = score.split("/")
        tb0 = games[0].find('(')
        if tb0 != -1:
            games[0] = games[0][:tb0]
        tb1 = games[1].find('(')
        if tb1 != -1:
            games[1] = games[1][:tb1]

        games[0], games[1] = int(games[0]), int(games[1])
        if games[0] > games[1]:
            return True
        if games[0] < games[1]:
            return False

        return -1


    def parseSets(self):
        numSetsWon = 0
        setWinners = []
        for score in self.score:
            winner = self._findSetWinner(score)
            setWinners.append(winner)
            if winner == -1:
                return -1, setWinners
            if winner:
                numSetsWon += 1
        
        numSets = numSetsWon * 2 - 1
        assert numSets in (1, 3, 5)
        return numSets, setWinners


def findDivider(text, s, start):
    d = text.find(s, start)
    if d == -1:
        return len(text), None
    return d, d + len(s)


def parseTitle(text):
    online = False
    d1, d1End = findDivider(text, " def. ", 0)
    winner = text[:d1]
    d2, d2End = findDivider(text, " : ", d1End)
    loser = text[d1End:d2]
    d3, d3End = findDivider(text, " - ", d2End)
    score = text[d2End:d3]
    score = score.split()
    d4, d4End = findDivider(text, " - ", d3End)
    court = text[d3End:d4]
    d5, d5End = findDivider(text, " (", d4End)
    time = text[d4End:d5]
    d6, d6End = findDivider(text, ") - ", d5End)
    fakeTime = text[d5End:d6]
    d7, d7End = findDivider(text, " [Online]", d6End)
    datetimeString = text[d6End:d7]
    
    if text.endswith("[Online]"):
        online = True
        winner = winner[:winner.index(" (ELO: ")]
        loser = loser[:loser.index(" (ELO: ")]

    return winner, loser, score, court, time, fakeTime, datetimeString, online


# TODO
def parseStats(stats, winner, loser):
    pass


def parseMatch(htmlMatch):
    text = htmlMatch.text
    winner, loser, score, court, time, fakeTime, datetimeString, online = parseTitle(text)

    winner = Player(winner)
    loser = Player(loser)

    stats = htmlMatch.find_next_sibling()
    assert stats.name == "table"
    parseStats(stats, winner, loser)
    
    match = Match(winner, loser, score, court, time, fakeTime, datetimeString, online)
    return match


def getLastMatchStats(soup, numMatches):
    global scriptDir
    tmpDir = f"{scriptDir}/tmp"
    images = []
    if numMatches <= 0:
        return images
    os.makedirs(tmpDir)
    hti = Html2Image(custom_flags=['--default-background-color=ffffff'], output_path=tmpDir,size=(1200, 500))
    for htmlMatch in soup('p')[-numMatches:]:
        matchStats = f"{htmlMatch}\n{htmlMatch.find_next_sibling()}<hr>"
        hti.screenshot(html_str=matchStats, css_str=str(soup.style), save_as='lastmatchstats.png')
        image = cv2.imread(f"{tmpDir}/lastmatchstats.png")
        os.remove(f"{tmpDir}/lastmatchstats.png")
        # image = image[:350,:1168]
        image = image[:350,:1200]
        images.append(image)
        if __name__ == "__main__":
            cv2.imshow("Image", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    os.rmdir(tmpDir)
    return images


def getMatchPlot(p1, p2, dates):
    plotMatchDiff = True
    fig = plt.figure(figsize=(15, 7))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title(f"{p1.name} vs {p2.name}")
    ax.set_xlabel("Date")
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    if plotMatchDiff:
        ax.set_ylabel("Win Difference")
        ax.step(dates, [a - b for a, b in zip(p1.numWins, p2.numWins)])
        ax.grid(which="major", axis='y', linestyle=':', linewidth="0.5", color="black")
    else:
        ax.set_ylabel("Number of Wins")
        ax.step(dates, p1.numWins, label=str(p1.name))
        ax.step(dates, p2.numWins, label=str(p2.name))
        ax.minorticks_on()
        ax.grid(which="major", axis='y', linestyle='-', linewidth="0.5", color="red")
        ax.grid(which="minor", axis='y', linestyle=':', linewidth="0.5", color="black")
        ax.legend()
    fig.canvas.draw()
    rgbaImage = np.array(fig.canvas.buffer_rgba())
    image = cv2.cvtColor(rgbaImage, cv2.COLOR_RGBA2BGR)
    plt.close(fig)
    if __name__ == "__main__":
        cv2.imshow("Image", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return image
    

def diff(h1, h2):
    d = h1 - h2
    if d > 0:
        return f"+{d}"
    return str(d)


def makePlural(s, num):
    return f"{num} {s}{"" if num == 1 else "s"}"


def outputLongestStreak(p, playerNumber, playerStreak, biggestStreak, playerStreakSets, biggestStreakSets):
    return f"{p.name[0]}'s Longest Streak: {makePlural("win", p.longestStreak)}; {makePlural("set", p.longestStreakSets)}" + \
    (" 🚀" if (playerStreak == playerNumber and biggestStreak) or (playerStreakSets == playerNumber and biggestStreakSets) else "")


def updateStreakVariables(playerNumber, p, playerStreak, streak, biggestStreak, sets=False):
    if playerStreak == playerNumber:
        streak += 1
    else:
        playerStreak = playerNumber
        streak = 1
        biggestStreak = False
    if not sets and streak > p.longestStreak:
        p.longestStreak = streak
        biggestStreak = True
    elif sets and streak > p.longestStreakSets:
        p.longestStreakSets = streak
        biggestStreak = True

    return playerStreak, streak, biggestStreak


def getPlayerNames(playerNum):
    which = "PLAYER_ONE" if playerNum == 1 else "PLAYER_TWO"
    envVar = os.getenv(which)
    if envVar is None:
        return None
    return [p.strip() for p in envVar.split(",")]


def getAllSameNames(name):
    envVar = os.getenv("SAME_NAME")
    if envVar is None:
        return [name]
    for group in envVar.split(";"):
        names = [p.strip() for p in group.split(",")]
        if name in names:
            return names
    return [name]


def processStats(numMatches=1):
    matchLogDir = os.getenv("MATCH_LOG_DIR")
    # sorting should read match logs in order since numbers are all 3 digits/zero padded
    matchLogs = sorted(f for f in os.listdir(matchLogDir) if f.startswith("MatchLog - TrainingClub"))
    done = False
    matches = []
    allUnknownSurfaces = set()
    for matchLog in matchLogs:
        assert not done
        with open(os.path.join(matchLogDir, matchLog)) as fp:
            soup = BeautifulSoup(fp, 'html.parser')
        
        first = True
        button = False
        done = True
        for htmlMatch in soup('p'):
            if first:
                first = False
                assert htmlMatch.input['type'] == "button"
                button = True
                continue
            if htmlMatch.text == "":
                button = False
                continue
            if htmlMatch.find('a') is not None:
                if not button: # this is a next. There is another html page. This should be the end of this file
                    done = False
                button = False
                continue

            button = False
            assert htmlMatch.input['type'] == "checkbox"
            match = parseMatch(htmlMatch)
            matches.append(match)
            if match.surface is None:
                allUnknownSurfaces.add(match.court)

    if len(allUnknownSurfaces) > 0:
        print(f"Unknown surface for courts {", ".join(allUnknownSurfaces)}")

    # TODO: Account for needing multiple soup files to get last numMatches matches
    lastMatchStats = getLastMatchStats(soup, numMatches)
    
    p1 = H2HPlayer(getPlayerNames(1))
    p2Names = getPlayerNames(2)
    if SHOWALLONLINE:
        p2Names = ["everyone online"]
    elif p2Names is None:
        lastMatch = matches[-1]
        if lastMatch.winner.name in p1.name:
            p2Names = getAllSameNames(lastMatch.loser.name)
        else:
            assert lastMatch.loser.name in p1.name
            p2Names = getAllSameNames(lastMatch.winner.name)
    p2 = H2HPlayer(p2Names)
    
    playerStreak = None
    streak = 0
    biggestStreak = False

    playerStreakSets = None
    streakSets = 0
    biggestStreakSets = False

    lastSurface = None
    unknownSurfaces = set()
    dates = []
    for match in matches:
        if SHOWALLONLINE:
            good = match.online and (match.winner.name in p1.name or match.loser.name in p1.name)
            if not good:
                continue
        else:
            good = match.winner.name in p1.name and match.loser.name in p2.name
            if not good:
                good = match.winner.name in p2.name and match.loser.name in p1.name
            if not good:
                continue
        # don't include retirements
        if match.numSets == -1:
            continue

        if match.numSets == 1 and not TRACKBO1:
            continue
        
        if match.winner.name in p1.name:
            setWinners = [1 if s else 2 for s in match.setWinners]
            playerStreak, streak, biggestStreak = updateStreakVariables(1, p1, playerStreak, streak, biggestStreak)
            p1.wins.append(match)
        else:
            setWinners = [2 if s else 1 for s in match.setWinners]
            playerStreak, streak, biggestStreak = updateStreakVariables(2, p2, playerStreak, streak, biggestStreak)
            p2.wins.append(match)

        p1.numWins.append(len(p1.wins))
        p2.numWins.append(len(p2.wins))
        dates.append(match.datetime)

        for s in setWinners:
            p = p1 if s == 1 else p2
            playerStreakSets, streakSets, biggestStreakSets = updateStreakVariables(s, p, playerStreakSets, streakSets, biggestStreakSets, True)

        assert playerStreak == playerStreakSets

        lastSurface = match.surface
        if match.surface is None:
            unknownSurfaces.add(match.court)

    matchPlot = getMatchPlot(p1, p2, dates)

    # ok if not perfect stats for showallonline
    if len(unknownSurfaces) > 0 and not SHOWALLONLINE:
        return f"Unknown surface for courts {", ".join(unknownSurfaces)}", [], None
    
    output = []
    output.append(f"{p1.name} vs {p2.name}")
    h1, h2 = len(p1.wins), len(p2.wins)
    output.append(f"Total H2H: {h1}-{h2} ({diff(h1, h2)})")
    if TRACKBO1:
        h1, h2 = p1.numBOSWins(1), p2.numBOSWins(1)
        output.append(f"BO1 H2H: {h1}-{h2} ({diff(h1, h2)})")
    h1, h2 = p1.numBOSWins(3), p2.numBOSWins(3)
    output.append(f"BO3 H2H: {h1}-{h2} ({diff(h1, h2)})")
    h1, h2 = p1.numBOSWins(5), p2.numBOSWins(5)
    output.append(f"BO5 H2H: {h1}-{h2} ({diff(h1, h2)})")
    
    # surfaces = ["Hard", "Clay", "Grass"]
    if lastSurface:
        sets = [1,3,5]
        if not TRACKBO1:
            sets.remove(1)
        for surface in [lastSurface]:
            output.append("")
            h1, h2 = p1.numSurfaceWins(surface), p2.numSurfaceWins(surface)
            output.append(f"{surface.capitalize()} H2H: {h1}-{h2} ({diff(h1, h2)})")
            for s in sets:
                h1, h2 = p1.numBOSSurfaceWins(s, surface), p2.numBOSSurfaceWins(s, surface)
                output.append(f"BO{s} {surface.capitalize()} H2H: {h1}-{h2} ({diff(h1, h2)})")

    output.append("")
    output.append(outputLongestStreak(p1, 1, playerStreak, biggestStreak, playerStreakSets, biggestStreakSets))
    output.append(outputLongestStreak(p2, 2, playerStreak, biggestStreak, playerStreakSets, biggestStreakSets))

    output.append("")
    output.append(f"{p1.name[0] if playerStreak == 1 else p2.name[0]}'s Streak: {makePlural("win", streak)}; {makePlural("set", streakSets)} 👑")
    
    return "\n".join(output), lastMatchStats, matchPlot

load_dotenv() # TODO: Maybe avoid calling multiple times
loadSurfaces()

if __name__ == "__main__":
    stats, lastMatchStats, matchPlot = processStats()
    print(stats)
