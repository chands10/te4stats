from bs4 import BeautifulSoup
from html2image import Html2Image
import os
from dotenv import load_dotenv
import cv2


scriptDir = os.path.dirname(os.path.abspath(__file__))


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
    
    
    def __str__(self):
        return str(vars(self))
    
    
    def numBOSWins(self, s):
        return len([w for w in self.wins if w.numSets == s])
    
    def numSurfaceWins(self, surface):
        return len([w for w in self.wins if w.surface == surface])
    
    def numBOSSurfaceWins(self, s, surface):
        return len([w for w in self.wins if w.numSets == s and w.surface == surface])


class Match:
    def __init__(self, winner, loser, score, court, time, fakeTime, datetime):
        self.winner = winner
        self.loser = loser
        self.score = score
        self.numSets = self.findNumSets()
        self.court = court
        self.surface = findSurface(court)
        self.time = time
        self.fakeTime = fakeTime
        self.datetime = datetime

        
    def __str__(self):
        return f"{str(self.winner)=}, {str(self.loser)=}, {str(vars(self))}"
    
    def findNumSets(self):
        numSetsWon = 0
        for score in self.score:
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
                numSetsWon += 1
            if games[0] == games[1]:
                return -1
        
        numSets = numSetsWon * 2 - 1
        assert numSets in (1, 3, 5)
        return numSets


def findDivider(text, s, start):
    d = text.find(s, start)
    if d == -1:
        return len(text), None
    return d, d + len(s)


def parseTitle(text):
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
    datetime = text[d6End:d7]
    
    if text.endswith("[Online]"):
        winner = winner[:winner.index(" (ELO: ")]
        loser = loser[:loser.index(" (ELO: ")]

    return winner, loser, score, court, time, fakeTime, datetime


# TODO
def parseStats(stats, winner, loser):
    pass


def parseMatch(htmlMatch):
    text = htmlMatch.text
    winner, loser, score, court, time, fakeTime, datetime = parseTitle(text)

    winner = Player(winner)
    loser = Player(loser)

    stats = htmlMatch.find_next_sibling()
    assert stats.name == "table"
    parseStats(stats, winner, loser)
    
    match = Match(winner, loser, score, court, time, fakeTime, datetime)
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
    

def diff(h1, h2):
    d = h1 - h2
    if d > 0:
        return f"+{d}"
    return str(d)


def processStats(numMatches=1):
    with open(os.getenv("MATCH_LOG")) as fp:
        soup = BeautifulSoup(fp, 'html.parser')
    
    first = True
    matches = []
    allUnknownSurfaces = set()
    for htmlMatch in soup('p'):
        if first:
            first = False
            assert htmlMatch.input['type'] == "button"
            continue
        
        assert htmlMatch.input['type'] == "checkbox"
        match = parseMatch(htmlMatch)
        matches.append(match)
        if match.surface is None:
            allUnknownSurfaces.add(match.court)

    if len(allUnknownSurfaces) > 0:
        print(f"Unknown surface for courts {", ".join(allUnknownSurfaces)}")

    lastMatchStats = getLastMatchStats(soup, numMatches)
    
    p1 = H2HPlayer(os.getenv("PLAYER_ONE").split(", "))
    p2 = H2HPlayer(os.getenv("PLAYER_TWO").split(", "))
    
    lastSurface = None
    playerStreak = None
    streak = 0
    unknownSurfaces = set()
    for match in matches:
        good = match.winner.name in p1.name and match.loser.name in p2.name
        if not good:
            good = match.winner.name in p2.name and match.loser.name in p1.name
        if not good:
            continue
        # don't include retirements
        if match.numSets == -1:
            continue
        
        if match.winner.name in p1.name:
            if playerStreak == 1:
                streak += 1
            else:
                playerStreak = 1
                streak = 1
            p1.wins.append(match)
        else:
            if playerStreak == 2:
                streak += 1
            else:
                playerStreak = 2
                streak = 1
            p2.wins.append(match)

        lastSurface = match.surface
        if match.surface is None:
            unknownSurfaces.add(match.court)

    if len(unknownSurfaces) > 0:
        return f"Unknown surface for courts {", ".join(unknownSurfaces)}", []

    
    output = []
    output.append(f"{p1.name} vs {p2.name}")
    h1, h2 = len(p1.wins), len(p2.wins)
    output.append(f"Total H2H: {h1}-{h2} ({diff(h1, h2)})")
    h1, h2 = p1.numBOSWins(1), p2.numBOSWins(1)
    output.append(f"BO1 H2H: {h1}-{h2} ({diff(h1, h2)})")
    h1, h2 = p1.numBOSWins(3), p2.numBOSWins(3)
    output.append(f"BO3 H2H: {h1}-{h2} ({diff(h1, h2)})")
    h1, h2 = p1.numBOSWins(5), p2.numBOSWins(5)
    output.append(f"BO5 H2H: {h1}-{h2} ({diff(h1, h2)})")
    
    # surfaces = ["Hard", "Clay", "Grass"]
    if lastSurface:
        for surface in [lastSurface]:
            output.append("")
            h1, h2 = p1.numSurfaceWins(surface), p2.numSurfaceWins(surface)
            output.append(f"{surface.capitalize()} H2H: {h1}-{h2} ({diff(h1, h2)})")
            for s in [1,3,5]:
                h1, h2 = p1.numBOSSurfaceWins(s, surface), p2.numBOSSurfaceWins(s, surface)
                output.append(f"BO{s} {surface.capitalize()} H2H: {h1}-{h2} ({diff(h1, h2)})")

    output.append("")
    output.append(f"{p1.name[0] if playerStreak == 1 else p2.name[0]}'s Streak: {streak} {"win 👑" if streak == 1 else "wins 👑"}")
    
    return "\n".join(output), lastMatchStats

load_dotenv() # TODO: Maybe avoid calling multiple times
loadSurfaces()

if __name__ == "__main__":
    stats, lastMatchStats = processStats()
    print(stats)
