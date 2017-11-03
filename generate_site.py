#! /usr/bin/env python3


# consultation-reforme-assemblee -- Fetch JSON data
# By: Emmanuel Raviart <emmanuel@raviart.com>
#
# Copyright (C) 2017 Emmanuel Raviart
# https://framagit.org/paula.forteza/consultation-reforme-assemblee-stats
#
# fetch-consultation-reforme-assemblee is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# fetch-consultation-reforme-assemblee is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http:>www.gnu.org/licenses/>.


"""Create a stats web site from data from "Consultation pour une nouvelle Assemblée nationale".

https://consultation.democratie-numerique.assemblee-nationale.fr/
"""


import argparse
from datetime import datetime
import json
import os
import shutil
import sys

from markupsafe import escape
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import rc
from mots_vides import stop_words
import pygit2
from wordcloud import WordCloud


label_by_comment_id = {
    '59f7251ae8a9656c1a8e7390': "Référendum d’initiative citoyenne",
    '59f72ac8e8a9656c1a8e73a9': "Assemblée constituante tirée au sort",
    '59de1a2866914e1e82238150': "Question citoyenne au gouvernement",
    '59db7d979e1c7be85124ddce': "Pétition > 100 000",
    '59dc72b49e1c7be85124e1f5': "Pédagogie des lois et de leurs processus",
    '59e3c9f166914e1e822387d5': "Pétitions comme en Suisse",
    '59e6681e66914e1e82238c7f': "Assemblée hors les murs",
    '59db7c979e1c7be85124ddbd': "Plateforme de consultation officielle",
    '59ebb2e966914e1e822395f4': "Votations et référendums obligatoires",
    '59db808a9e1c7be85124dde0': "Scrutins au jugement majoritaire",
    '59db8cd49e1c7be85124deb0': "Référendums d'initiative populaire et locaux",
    '59e8c9a766914e1e822390fa': "Référendum révocatoire",
    '59e31ef666914e1e822386a0': "Débats plutôt que référendums",
    '59db85cf9e1c7be85124de62': "Changement de constitution",
    }
mots_creux = stop_words('fr')
replies_by_comment_id = {}
scores_by_comment_id = {}


def get_label_with_replies_count(comment_id):
    label = label_by_comment_id.get(comment_id)
    if label is None:
        return None
    replies = replies_by_comment_id[comment_id]
    return '{} : {}'.format(label, replies[-1][1])


def get_label_with_score(comment_id):
    label = label_by_comment_id.get(comment_id)
    if label is None:
        return None
    scores = scores_by_comment_id[comment_id]
    return '{} : {}'.format(label, scores[-1][1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'repo_dir',
        help='path of Git data repository',
        )
    parser.add_argument(
        'html_dir',
        help='path of data directory',
        )
    args = parser.parse_args()

    repo = pygit2.Repository(args.repo_dir)
    if not os.path.exists(args.html_dir):
        os.mkdir(args.html_dir)
    images_dir = os.path.join(args.html_dir, 'images')
    if not os.path.exists(images_dir):
        os.mkdir(images_dir)

    comment_by_id = {}
    comment_ids_by_topic_id = {}
    topic_by_id = {}
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL  | pygit2.GIT_SORT_REVERSE):
        comment_ids_by_topic_id = {}
        for entry in commit.tree:
            if entry.type == 'tree':
                # print(entry.id, entry.type, entry.name)
                topic_tree = repo[entry.id]
                topic_blob = repo[topic_tree['topic.json'].id]
                topic = json.loads(topic_blob.data.decode('utf-8'))
                topic_by_id[topic['id']] = topic
                # print()
                # print(topic['mediaTitle'])
                comments_tree = repo[topic_tree['comments'].id]
                for comment_entry in comments_tree:
                    comment_blob = repo[comment_entry.id]
                    comment = json.loads(comment_blob.data.decode('utf-8'))
                    # print('----')
                    # print(comment['text'])
                    comment_by_id[comment['id']] = comment
                    comment_ids_by_topic_id.setdefault(topic['id'], []).append(comment['id'])
                    replies_by_comment_id.setdefault(comment['id'], []).append((commit.commit_time, comment['repliesCount']))
                    scores_by_comment_id.setdefault(comment['id'], []).append((commit.commit_time, comment['score']))

    comments_sorted_by_replies = sorted(
        replies_by_comment_id.items(),
        key = lambda comment_id_and_replies: comment_id_and_replies[1][-1][1],
        reverse=True,
        )
    comments_sorted_by_score = sorted(
        scores_by_comment_id.items(),
        key = lambda comment_id_and_scores: comment_id_and_scores[1][-1][1],
        reverse=True,
        )

    for topic in topic_by_id.values():
        comment_ids = comment_ids_by_topic_id[topic['id']]
        comments = [
            comment_by_id[comment_id]
            for comment_id in comment_ids
            ]
        comments = sorted(comments, key=lambda comment: comment['score'], reverse=True)

        rc('font', size=20)
        figure, axes = plt.subplots(1, figsize=(16, 12))
        figure.autofmt_xdate()
        topic_comments_sorted_by_score = [
            (comment_id, scores)
            for comment_id, scores in comments_sorted_by_score
            if comment_id in comment_ids
            ]
        for comment_id, scores in topic_comments_sorted_by_score:
            x = [
                datetime.fromtimestamp(epoch)
                for epoch, score in scores
                ]
            y = [
                score
                for period, score in scores
                ]
            plt.plot(x, y, label=get_label_with_score(comment_id))
        plt.xlabel('Date')
        plt.ylabel('Score')
        plt.title('Score par commentaire')
        x_formatter = mdates.DateFormatter('%d-%m')
        axes.xaxis.set_major_formatter(x_formatter)
        plt.legend()
        plt.savefig(os.path.join(images_dir, 'topic-scores-{}.png'.format(topic['id'])))
        plt.close()

        rc('font', size=20)
        figure, axes = plt.subplots(1, figsize=(16, 12))
        figure.autofmt_xdate()
        topic_comments_sorted_by_replies = [
            (comment_id, replies)
            for comment_id, replies in comments_sorted_by_replies
            if comment_id in comment_ids
            ]
        for comment_id, replies in topic_comments_sorted_by_replies[:10]:
            x = [
                datetime.fromtimestamp(epoch)
                for epoch, epoch_replies in replies
                ]
            y = [
                epoch_replies
                for period, epoch_replies in replies
                ]
            plt.plot(x, y, label=get_label_with_replies_count(comment_id))
        plt.xlabel('Date')
        plt.ylabel('Réponses')
        plt.title('Nombre de réponses par commentaire')
        x_formatter = mdates.DateFormatter('%d-%m')
        axes.xaxis.set_major_formatter(x_formatter)
        plt.legend()
        plt.savefig(os.path.join(images_dir, 'topic-replies-{}.png'.format(topic['id'])))
        plt.close()

        comments_texts = []
        replies_texts = []
        for comment_id in comment_ids:
            comment = comment_by_id[comment_id]
            comments_texts.append(comment['text'])
            for reply in comment['replies']:
                replies_texts.append(reply['text'])

        text = mots_creux.rebase('\n'.join(comments_texts), '')
        wordcloud = WordCloud(max_font_size=40).generate(text)
        plt.figure(figsize=(16, 12))
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        plt.savefig(os.path.join(images_dir, 'topic-comments-word-cloud-{}.png'.format(topic['id'])), bbox_inches='tight')
        plt.close()

        text = mots_creux.rebase('\n'.join(replies_texts), '')
        wordcloud = WordCloud(max_font_size=40).generate(text)
        plt.figure(figsize=(16, 12))
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        plt.savefig(os.path.join(images_dir, 'topic-replies-word-cloud-{}.png'.format(topic['id'])), bbox_inches='tight')
        plt.close()

        html_file_path = os.path.join(args.html_dir, '{}.html'.format(topic['id']))
        with open(html_file_path, 'w', encoding='utf-8') as html_file:
            html_file.write("""
<!DOCTYPE html>
<html id="html-element" lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>{title}</title>
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta.2/css/bootstrap.min.css" integrity="sha384-PsH8R72JQ3SOdhVi3uxftmaW6Vc51MKb0q5P2rRUpPvrszuE4W1povHYgTpBfshb" crossorigin="anonymous">
  </head>
  <body>
    <h2>Quel rôle pour les citoyens dans l’élaboration et l’application de la loi ?</h2>
    <h3>Consultation pour une nouvelle Assemblée nationale</h3>
    <h1>{title}</h1>
    {clauses}
    <hr>
    <h2>Commentaires</h2>
    <p><img src="images/topic-scores-{topic_id}.png"></p>
    <p><img src="images/topic-replies-{topic_id}.png"></p>
    <ul class="list-group">
        {comments}
    </ul>
    <h2>Mots des commentaires</h2>
    <p><img src="images/topic-comments-word-cloud-{topic_id}.png"></p>
    <h2>Mots des réponses</h2>
    <p><img src="images/topic-replies-word-cloud-{topic_id}.png"></p>
    <script src="https://code.jquery.com/jquery-3.2.1.slim.min.js" integrity="sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN" crossorigin="anonymous"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.12.3/umd/popper.min.js" integrity="sha384-vFJXuSJphROIrBnz7yo7oB41mKfc8JzQZiCq4NCceLEaO4IHwicKwpJf9c9IpFgh" crossorigin="anonymous"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta.2/js/bootstrap.min.js" integrity="sha384-alpBpkh1PFOepccYVYDB4do5UnbKysX5WZXm3XxPqe5iKTfUKjNkCk9SaVuEZflJ" crossorigin="anonymous"></script>  </body>
</html>
""".format(
        clauses='\n'.join(
            clause['markup']
            for clause in topic['clauses']
            ),
        comments='\n'.join(
            '<li class="list-group-item">{}</li>'.format('\n'.join(
                '<p>{}</p>\n'.format(escape(line))
                for line in comment['text'].split('\n')
                ) + '\n<p>Score : {} / Réponses : {}</p>\n'.format(comment['score'], comment['repliesCount']))
            for comment in comments
            ),
        title=escape(topic['mediaTitle']),
        topic_id=topic['id'],
        ))

    # Main page

    comments = list(comment_by_id.values())
    comments = sorted(comments, key=lambda comment: comment['score'], reverse=True)

    rc('font', size=20)
    figure, axes = plt.subplots(1, figsize=(16, 12))
    figure.autofmt_xdate()
    for comment_id, scores in comments_sorted_by_score:
        x = [
            datetime.fromtimestamp(epoch)
            for epoch, score in scores
            ]
        y = [
            score
            for period, score in scores
            ]
        plt.plot(x, y, label=get_label_with_score(comment_id))
    plt.xlabel('Date')
    plt.ylabel('Score')
    plt.title('Score par commentaire')
    x_formatter = mdates.DateFormatter('%d-%m')
    axes.xaxis.set_major_formatter(x_formatter)
    plt.legend()
    plt.savefig(os.path.join(images_dir, 'scores.png'))
    plt.close()

    rc('font', size=20)
    figure, axes = plt.subplots(1, figsize=(16, 12))
    figure.autofmt_xdate()
    for comment_id, replies in comments_sorted_by_replies[:10]:
        x = [
            datetime.fromtimestamp(epoch)
            for epoch, epoch_replies in replies
            ]
        y = [
            epoch_replies
            for period, epoch_replies in replies
            ]
        plt.plot(x, y, label=get_label_with_replies_count(comment_id))
    plt.xlabel('Date')
    plt.ylabel('Réponses')
    plt.title('Nombre de réponses par commentaire')
    x_formatter = mdates.DateFormatter('%d-%m')
    axes.xaxis.set_major_formatter(x_formatter)
    plt.legend()
    plt.savefig(os.path.join(images_dir, 'replies.png'))
    plt.close()

    comments_texts = []
    replies_texts = []
    for comment in comments:
        comments_texts.append(comment['text'])
        for reply in comment['replies']:
            replies_texts.append(reply['text'])

    text = mots_creux.rebase('\n'.join(comments_texts), '')
    wordcloud = WordCloud(max_font_size=40).generate(text)
    plt.figure(figsize=(16, 12))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.savefig(os.path.join(images_dir, 'comments-word-cloud.png'), bbox_inches='tight')
    plt.close()

    text = mots_creux.rebase('\n'.join(replies_texts), '')
    wordcloud = WordCloud(max_font_size=40).generate(text)
    plt.figure(figsize=(16, 12))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.savefig(os.path.join(images_dir, 'replies-word-cloud.png'), bbox_inches='tight')
    plt.close()

    html_file_path = os.path.join(args.html_dir, 'index.html')
    with open(html_file_path, 'w', encoding='utf-8') as html_file:
        html_file.write("""
<!DOCTYPE html>
<html id="html-element" lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Consultation pour une nouvelle Assemblée nationale</title>
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta.2/css/bootstrap.min.css" integrity="sha384-PsH8R72JQ3SOdhVi3uxftmaW6Vc51MKb0q5P2rRUpPvrszuE4W1povHYgTpBfshb" crossorigin="anonymous">
  </head>
  <body>
    <h1>Quel rôle pour les citoyens dans l’élaboration et l’application de la loi ?</h1>
    <h2>Consultation pour une nouvelle Assemblée nationale</h2>
    <p><img src="images/scores.png"></p>
    <p><img src="images/replies.png"></p>
    <ul class="list-group">
        {topics}
    </ul>
    <br><br><br><br>
    <h2>Mots des commentaires</h2>
    <p><img src="images/comments-word-cloud.png"></p>
    <h2>Mots des réponses</h2>
    <p><img src="images/replies-word-cloud.png"></p>
    <script src="https://code.jquery.com/jquery-3.2.1.slim.min.js" integrity="sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN" crossorigin="anonymous"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.12.3/umd/popper.min.js" integrity="sha384-vFJXuSJphROIrBnz7yo7oB41mKfc8JzQZiCq4NCceLEaO4IHwicKwpJf9c9IpFgh" crossorigin="anonymous"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta.2/js/bootstrap.min.js" integrity="sha384-alpBpkh1PFOepccYVYDB4do5UnbKysX5WZXm3XxPqe5iKTfUKjNkCk9SaVuEZflJ" crossorigin="anonymous"></script>  </body>
</html>
""".format(
    topics='\n'.join(
        '<li class="list-group-item"><a href="{}.html">{}</a></li>'.format(topic['id'], escape(topic['mediaTitle']))
        for topic in sorted(topic_by_id.values(), key=lambda topic: topic['id'], reverse=True)
        ),
    ))

    return 0


if __name__ == '__main__':
    sys.exit(main())
